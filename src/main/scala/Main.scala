import java.io._
import java.nio.charset.StandardCharsets

import org.apache.http.HttpStatus
import org.apache.http.client.methods.HttpGet
import org.apache.http.impl.client.HttpClients
import org.apache.http.util.EntityUtils
import org.joda.time.{DateTime, Duration}
import play.api.libs.json._

import scala.io.Source
import scala.util.matching.Regex

object Main extends App {
  private val ENCODING = "UTF-8"

  def getActionsFromCache(filePath: String): JsArray = {
    val actionsFile = Source.fromFile(filePath, ENCODING)
    val actionsStringBuffer = new StringBuffer
    try {
      for (line <- actionsFile.getLines) {
        actionsStringBuffer.append(line)
      }
    }
    finally {
      actionsFile.close
    }
    val actionsString = actionsStringBuffer.toString
    Json.parse(actionsString).as[JsArray]
  }

  def fetchActions(userName: String, apiKey: String, apiSecret: String): JsArray = {
    val requestUrl = s"https://api.trello.com/1/members/$userName/actions?key=$apiKey&token=$apiSecret&limit=100"

    val charset = StandardCharsets.UTF_8
    val httpClient = HttpClients.createDefault()
    val request = new HttpGet(requestUrl)

    val response = httpClient.execute(request)

    val status = response.getStatusLine().getStatusCode()
    val actionsString = status match {
      case HttpStatus.SC_OK => EntityUtils.toString(response.getEntity(), charset)
      case _ => ""
    }

    try {
      if (response != null) {
        response.close()
      }
      if (httpClient != null) {
        httpClient.close()
      }
    }
    catch {
      case e: IOException => e.printStackTrace()
    }

    Json.parse(actionsString).as[JsArray]
  }

  val TRELLO_COMMENT_BY_PLUS = new Regex("""plus! (\d+\.\d+)/(\d+\.\d+) (.*)""", "spent", "estimated", "comment")

  def getFilteredActions(actions: JsArray, boardName: String, currentDateString: String) = {
    actions.value.filter {
      action =>
        (action \ "data" \ "board" \ "name").as[String] == boardName &&
          (action \ "date").as[String].startsWith(currentDateString) &&
          (action \ "type").as[String] == "commentCard"
    }.map {
      action => {
        val matched = TRELLO_COMMENT_BY_PLUS.findFirstMatchIn((action \ "data" \ "text").as[String]).get
        Map(
          "title" -> (action \ "data" \ "card" \ "name").as[String],
          "spent" -> matched.group("spent").toFloat,
          "task" -> matched.group("comment"),
        )
      }
    }
  }

  def getConverter(filePath: String): JsArray = {
    val dictFile = Source.fromFile(filePath, ENCODING)
    val dictStringBuffer = new StringBuffer
    try {
      for (line <- dictFile.getLines) {
        dictStringBuffer.append(line)
      }
    }
    finally {
      dictFile.close
    }
    val dictString = dictStringBuffer.toString
    Json.parse(dictString).as[JsArray]
  }

  val IS_DEBUG = System.getenv("IS_DEBUG") match {
    case "true" => true
    case _ => false
  }

  val actionsFile = Source.fromFile("trello_settings.txt", ENCODING)
  val trelloEnvironments = actionsFile.getLines.toArray
  actionsFile.close

  val TRELLO_API_KEY = trelloEnvironments(0)
  val TRELLO_API_SECRET = trelloEnvironments(1)
  val TRELLO_USER_NAME = trelloEnvironments(2)
  val TRELLO_BOARD_NAME = trelloEnvironments(3)

  val actions: JsArray = if (IS_DEBUG) {
    getActionsFromCache("actions_debug.json")
  } else {
    fetchActions(TRELLO_USER_NAME, TRELLO_API_KEY, TRELLO_API_SECRET)
  }

  val currentDateTime = new DateTime
  val endDateTime = currentDateTime
    .withTime(currentDateTime.getHourOfDay, currentDateTime.getMinuteOfHour, 0, 0)
    .plusMinutes(15 - currentDateTime.getMinuteOfHour % 15)
  val currentDateString = if (IS_DEBUG) {
    "2019-02-28"
  } else {
    endDateTime.toString("yyyy-MM-dd")
  }

  val filteredActions = getFilteredActions(actions, TRELLO_BOARD_NAME, currentDateString)

  val DICTIONARY_PATH = if (IS_DEBUG) "dictionary_debug.json" else "dictionary.json"
  val dict: JsArray = getConverter(DICTIONARY_PATH)

  val itemList = dict.as[JsArray].value.map {
    item => {
      val actions = filteredActions.filter {
        action => action("title") == (item \ "trello" \ "title").as[String]
      }
      val spentRaw = actions.foldLeft(0.0)((x, y) => x + y("spent").toString.toFloat)
      val spentFixed = scala.math.ceil(spentRaw / 0.25) * 0.25
      val tasks = actions.map {
        action => action("task")
      }.toSet.toList

      Map(
        "section" -> (item \ "daily_report" \ "section").as[String],
        "title" -> (item \ "daily_report" \ "title").as[String],
        "spent" -> spentFixed,
        "actions" -> tasks,
      )
    }
  }

  val offsetItemList = (itemList :+ Map(
    "section" -> "その他",
    "title" -> "日報作成、工数入力",
    "spent" -> "0.25",
    "actions" -> null,
  )).toList ::: (currentDateTime.getDayOfWeek match {
    case 1 => List[Map[String, Object]](
      Map(
        "section" -> "その他",
        "title" -> "本社朝礼",
        "spent" -> "0.25",
        "actions" -> null,
      ),
      Map(
        "section" -> "その他",
        "title" -> "CBU開発定例",
        "spent" -> "0.5",
        "actions" -> null,
      ),
      Map(
        "section" -> "その他",
        "title" -> "課定例",
        "spent" -> "0.5",
        "actions" -> null,
      )
    )
    case _ => Nil
  })

  val sumSpentActual = offsetItemList.foldLeft(0.0)((x, y) => x + y("spent").toString.toFloat)
  val startDateTime = currentDateTime.withTime(10, 0, 0, 0)
  val durationTime = new Duration(startDateTime, endDateTime)
  val sumSpentExpected = if (IS_DEBUG) {
    11.25
  } else {
    scala.math.ceil((durationTime.getStandardMinutes / 60.0 - 1.0) / 0.25) * 0.25
  }
  val deltaSumSpent = sumSpentExpected - sumSpentActual

  val sortedItemList = offsetItemList.sortBy(s => -s("spent").toString.toFloat)
  val fixedItemList = sortedItemList.zipWithIndex.map {
    case (item, index) => index match {
      case 0 => Map(
        "section" -> item("section"),
        "title" -> item("title"),
        "spent" -> ((item("spent").toString.toFloat + deltaSumSpent) / 0.25).toInt * 0.25,
        "actions" -> item("actions"),
      )
      case _ => item
    }
  }

  val sectionList = dict.value.map {
    item => (item \ "daily_report" \ "section").as[String]
  }.toSet.toList
  val buildItemList = sectionList.map {
    section =>
      Map(
        "name" -> section,
        "items" -> fixedItemList.filter {
          item => item("section") == section
        }.map {
          item =>
            Map(
              "title" -> item("title"),
              "spent" -> item("spent"),
              "actions" -> item("actions"),
            )
        }.filter {
          item => item("spent") != 0.0
        }
      )
  }.filter {
    case sectionMap: Map[String, Object] => sectionMap("items") match {
      case items: List[Map[String, Object]] => items.nonEmpty
      case _ => false
    }
    case _ => false
  }

  val mailContents = buildItemList.foldLeft("")((x, y) => {
    x + s"【${y("name")}】\n" + (y("items") match {
      case items: List[Map[String, Object]] =>
        items.foldLeft("")((z, w) => {
          z + f"[中][${w("spent").toString.toFloat}%.2fh] ${w("title")}\n" + (w("actions") match {
            case actions: List[String] =>
              actions.foldLeft("")((a, b) => s"$a・$b\n")
            case _ => ""
          })
        })
      case _ => ""
    }) + "\n"
  })

  val todayTasksFile = new PrintWriter(new BufferedWriter(new OutputStreamWriter(new FileOutputStream("today_tasks.txt"), ENCODING)))
  todayTasksFile.write(mailContents)
  todayTasksFile.close()
}
