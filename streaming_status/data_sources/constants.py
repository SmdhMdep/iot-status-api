# things attribute names
class ThingAttributeNames:
    REGISTRATION_WAY = 'RegistrationWay'
    SENSOR_PROVIDER = 'SensorProvider'
    SENSOR_ORGANIZATION = 'SensorOrganization'
    CUSTOM_LABEL = 'CustomLabel'

# fleet index disconnect reasons
DISCONNECT_REASON_DESCRIPTIONS = {
    'AUTH_ERROR': 'The client failed to authenticate or authorization failed.',
    'CLIENT_ERROR': 'The client did something wrong that causes it to disconnect. '
                    'For example, a client will be disconnected for sending more '
                    'than 1 MQTT CONNECT packet on the same connection or if the '
                    'client attempts to publish with a payload that exceeds the '
                    'payload limit.',
    'CLIENT_INITIATED_DISCONNECT': 'The client indicates that it will disconnect. '
                                    'The client can do this by sending either a '
                                    'MQTT DISCONNECT control packet or a Close '
                                    'frame if the client is using a WebSocket '
                                    'connection.',
    'CONNECTION_LOST': 'The client-server connection is cut off. This can happen '
                        'during a period of high network latency or when the '
                        'internet connection is lost.',
    'DUPLICATE_CLIENTID': 'The client is using a client ID that is already in '
                        'use. In this case, the client that is already '
                        'connected will be disconnected with this disconnect '
                        'reason.',
    'FORBIDDEN_ACCESS': 'The client is not allowed to be connected. For example, '
                        'a client with a denied IP address will fail to connect.',
    'MQTT_KEEP_ALIVE_TIMEOUT': 'If there is no client-server communication for '
                                "1.5x of the client's keep-alive time, the client "
                                'is disconnected.',
    'SERVER_ERROR': 'Disconnected due to unexpected server issues.',
    'SERVER_INITIATED_DISCONNECT': 'Server intentionally disconnects a client for '
                                    'operational reasons.',
    'THROTTLED': 'The client is disconnected for exceeding a throttling limit.',
    'WEBSOCKET_TTL_EXPIRATION': 'The client is disconnected because a WebSocket '
                                'has been connected longer than its time-to-live '
                                'value.'
}
