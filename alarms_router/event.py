from typing import TypedDict, Literal


EventTimestamp = int
"""Milliseconds since epoch."""

DisconnectionNotificationMetricValue = TypedDict(
    "DisconnectionNotificationMetricValue",
    {"count": int},
)

DisconnectionNotificationCriteria = TypedDict("DisconnectionNotificationCriteria", {
        "consecutiveDatapointsToClear": int,
        "value": 'DisconnectionNotificationMetricValue',
        "consecutiveDatapointsToAlarm": int,
        "comparisonOperator": Literal["less-than-equals"],
})

DisconnectionNotification = TypedDict("DisconnectionNotification", {
    "violationEventTime": EventTimestamp,
    "thingName": str,
    "criteria": DisconnectionNotificationCriteria,
    "securityProfileName": str,
    "violationEventType": Literal["in-alarm", "alarm-cleared", "alarm-invalidated"],
    "metricValue": DisconnectionNotificationMetricValue,
})
