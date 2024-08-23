import base64
import json
from datetime import datetime, timedelta

import boto3

from ..config import config
from ..utils import AppError

CONNECT = "Connect"
PUBLISH_IN = "Publish-In"
DISCONNECT = "Disconnect"

METRICS_NAMESPACE = "SMDH/Prod/IoT"

iot_client = boto3.client("iot", region_name=config.fleet_index_iot_region_name)
cloudwatch_client = boto3.client("cloudwatch", region_name=config.fleet_index_iot_region_name)


def _metric_identity(metric_name: str, device_name: str) -> dict:
    return {
        "Namespace": METRICS_NAMESPACE,
        "MetricName": metric_name,
        "Dimensions": [
            {
                "Name": "Client ID",
                "Value": device_name,
            },
        ],
    }


def get_activity_metric(device_name: str, date_range: tuple[datetime, datetime]):
    # TODO rounding of start and end times and adjusting period accordingly, see boto3 docs
    result = cloudwatch_client.get_metric_data(
        MetricDataQueries=[
            {
                "Id": "publish",
                "MetricStat": {
                    "Metric": _metric_identity("PublishIn.Success", device_name),  # type: ignore
                    # data is available for 15 days
                    "Period": 60,
                    "Stat": "SampleCount",
                },
                "ReturnData": True,
            },
        ],
        StartTime=date_range[0],
        EndTime=date_range[1],
        ScanBy="TimestampDescending",
        LabelOptions={"Timezone": "+0000"},
    )

    # TODO pagination, logging of messages and errors depending on `StatusCode`.
    metric = result["MetricDataResults"][0]
    return {
        "values": metric["Values"],
        "timestamps": list(map(datetime.timestamp, metric["Timestamps"])),
    }


def get_connectivity_metric(
    device_name: str,
    date_range: tuple[datetime, datetime],
    page: str | None = None,
):
    params: dict = {}
    if page is not None:
        page_params = json.loads(base64.decodebytes(page.encode()).decode())
        params = {
            "nextToken": page_params["nextToken"],
            "startTime": datetime.fromtimestamp(page_params["startTime"]),
            "endTime": datetime.fromtimestamp(page_params["endTime"]),
        }
    else:
        # data is available for 14 days and request period must be within 2 weeks.
        start_date, end_date = date_range
        if start_date > end_date:
            raise AppError.invalid_argument("start date must be before end date")

        now = datetime.now()
        two_weeks_delta = timedelta(days=14)

        if now - start_date > two_weeks_delta:
            start_date = now - two_weeks_delta

        if end_date > now or end_date < start_date:
            end_date = now

        params["startTime"] = start_date
        params["endTime"] = end_date

    response = iot_client.list_metric_values(
        thingName=device_name,
        metricName="aws:disconnect-duration",
        **params,
    )

    values, timestamps = [], []
    for data in response["metricDatumList"]:
        values.append(data["value"]["count"])
        timestamps.append(data["timestamp"].timestamp())

    next_page = None
    if "nextToken" in response:
        params = {
            "nextToken": response["nextToken"],
            "startTime": params["startTime"].timestamp(),
            "endTime": params["endTime"].timestamp(),
        }
        next_page = base64.encodebytes(json.dumps(params).encode()).decode()

    return {
        "values": values,
        "timestamps": timestamps,
        "nextPage": next_page,
    }
