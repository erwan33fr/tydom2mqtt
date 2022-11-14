from alarm_control_panel import Alarm
from sensors import sensor


from http.server import BaseHTTPRequestHandler
from http.client import HTTPResponse
import urllib3
from io import BytesIO
import json
import sys

from logger import logger
import logging

logger = logging.getLogger(__name__)


# Dicts
deviceAlarmKeywords = [
    'alarmMode',
    'alarmState',
    'alarmTechnical',
    'alarmSOS',
    'unitBatteryDefect',
    'unitAutoProtect',
    'unitInternalDefect',
    'systAlarmDefect',
    'systAutoProtect',
    'systBatteryDefect',
    'systSupervisionDefect',
    'systOpenIssue',
    'systSectorDefect',
    'systTechnicalDefect',
    'outTemperature',
    'part1State',
    'part2State',
    'part3State',
    'part4State']


# Device dict for parsing
device_name = dict()
device_endpoint = dict()
device_type = dict()


class TydomMessageHandler():

    def __init__(self, incoming_bytes, tydom_client, mqtt_client):
        self.incoming_bytes = incoming_bytes
        self.tydom_client = tydom_client
        self.cmd_prefix = tydom_client.cmd_prefix
        self.mqtt_client = mqtt_client


    async def incomingTriage(self):
        bytes_str = self.incoming_bytes
        # If not MQTT client, return incoming message to use it with anything.
        if self.mqtt_client is None:
            return bytes_str
        else:
            incoming = None
            first = str(bytes_str[:40])  # Scanning 1st characters
            try:
                if ("Uri-Origin: /refresh/all" in first in first):
                    pass
                elif ("PUT /devices/data" in first) or ("/devices/cdata" in first):
                    logger.debug('PUT /devices/data message detected !')
                    try:
                        incoming = self.parse_put_response(bytes_str)
                        await self.parse_response(incoming)
                    except BaseException:
                        logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                        logger.error('RAW INCOMING :')
                        logger.error(bytes_str)
                        logger.error('END RAW')
                        logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                elif ("scn" in first):
                    try:
                        incoming = get(bytes_str)
                        await self.parse_response(incoming)
                        logger.info('Scenarii message processed !')
                        logger.info("##################################")
                    except BaseException:
                        logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                        logger.error('RAW INCOMING :')
                        logger.error(bytes_str)
                        logger.error('END RAW')
                        logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                elif ("POST" in first):
                    try:
                        incoming = self.parse_put_response(bytes_str)
                        await self.parse_response(incoming)
                        logger.info('POST message processed !')
                    except BaseException:
                        logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                        logger.error('RAW INCOMING :')
                        logger.error(bytes_str)
                        logger.error('END RAW')
                        logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                elif ("HTTP/1.1" in first):  # (bytes_str != 0) and
                    response = self.response_from_bytes(
                        bytes_str[len(self.cmd_prefix):])
                    incoming = response.data.decode("utf-8")
                    try:
                        await self.parse_response(incoming)
                    except BaseException:
                        logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                        logger.error('RAW INCOMING :')
                        logger.error(bytes_str)
                        logger.error('END RAW')
                        logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                else:
                    logger.warn("Didn't detect incoming type, here it is :")
                    logger.warn(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                    logger.warn('RAW INCOMING :')
                    logger.warn(bytes_str)
                    logger.warn('END RAW')
                    logger.warn(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

            except Exception as e:
                logger.error("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                logger.error('receiveMessage error')
                logger.error('RAW :')
                logger.error(bytes_str)
                logger.error("Incoming payload :")
                logger.error(incoming)
                logger.error("Error :")
                logger.error(e)
                logger.error('Exiting to ensure systemd restart....')
                sys.exit()  # Exit all to ensure systemd restart


    # Basic response parsing. Typically GET responses + instanciate covers and
    # alarm class for updating data
    async def parse_response(self, incoming):
        data = incoming
        msg_type = None

        first = str(data[:40])
        # Detect type of incoming data
        if (data != ''):
            # search for id_catalog in all data to be sure to get configuration
            # detected
            if ("id_catalog" in data):
                logger.debug(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                logger.debug('Incoming message type : config detected')
                msg_type = 'msg_config'
                logger.debug(data)
            elif ("cmetadata" in data):
                logger.debug(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                logger.debug('Incoming message type : cmetadata detected')
                msg_type = 'msg_cmetadata'
                logger.debug(data)
            elif ("cdata" in data):
                logger.debug(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                logger.debug('Incoming message type : cdata detected')
                msg_type = 'msg_cdata'
                logger.debug(data)
            elif ("id" in first):
                logger.debug(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                logger.debug('Incoming message type : data detected')
                msg_type = 'msg_data'
                logger.debug(data)
            elif ("doctype" in first):
                logger.debug('Incoming message type : html detected (probable 404)')
                msg_type = 'msg_html'
                logger.debug(data)
            elif ("productName" in first):
                logger.debug(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                logger.debug('Incoming message type : Info detected')
                msg_type = 'msg_info'
                logger.debug(data)
            else:
                logger.debug('Incoming message type : no type detected')
                logger.debug(data)

            if not (msg_type is None):
                try:
                    if (msg_type == 'msg_config'):
                        parsed = json.loads(data)
                        # logger.debug(parsed)
                        await self.parse_config_data(parsed=parsed)
                    elif (msg_type == 'msg_cmetadata'):
                        parsed = json.loads(data)
                        # logger.debug(parsed)
                        await self.parse_cmeta_data(parsed=parsed)
                    elif (msg_type == 'msg_cdata'):
                        parsed = json.loads(data)
                        # logger.debug(parsed)
                        await self.parse_devices_cdata(parsed=parsed)
                    elif (msg_type == 'msg_data'):
                        parsed = json.loads(data)
                        # logger.debug(parsed)
                        await self.parse_devices_data(parsed=parsed)
                    elif (msg_type == 'msg_html'):
                        logger.debug("HTML Response ?")
                    elif (msg_type == 'msg_info'):
                        pass
                    else:
                        # Default json dump
                        logger.debug()
                        logger.debug(
                            json.dumps(
                                parsed,
                                sort_keys=True,
                                indent=4,
                                separators=(
                                    ',',
                                    ': ')))
                except Exception as e:
                    logger.error('Cannot parse response !')
                    # logger.error('Response :')
                    # logger.error(data)
                    if (e != 'Expecting value: line 1 column 1 (char 0)'):
                        logger.error("Error : ", e)
                        logger.error(parsed)
            logger.info('Incoming data parsed successfully !')
            return(0)


    async def parse_config_data(self, parsed):
        for i in parsed["endpoints"]:
            # Get list of shutter
            # logger.debug(i)
            device_unique_id = str(i["id_endpoint"]) + \
                "_" + str(i["id_device"])

            if i["last_usage"] == 'alarm':
                # logger.debug('%s %s'.format(i["id_endpoint"], i["name"]))
                device_name[device_unique_id] = "Tyxal Alarm"
                device_type[device_unique_id] = 'alarm'
                device_endpoint[device_unique_id] = i["id_endpoint"]

        logger.info('Configuration updated')


    async def parse_cmeta_data(self, parsed):
        for i in parsed:
            for endpoint in i["endpoints"]:
                if len(endpoint["cmetadata"]) > 0:
                    for elem in endpoint["cmetadata"]:
                        device_id = i["id"]
                        endpoint_id = endpoint["id"]
                        unique_id = str(endpoint_id) + "_" + str(device_id)

        logger.info('Metadata configuration updated')


    async def parse_devices_cdata(self, parsed):
        for i in parsed:
            for endpoint in i["endpoints"]:
                if endpoint["error"] == 0 and len(endpoint["cdata"]) > 0:
                    try:
                        device_id = i["id"]
                        endpoint_id = endpoint["id"]
                        unique_id = str(endpoint_id) + "_" + str(device_id)
                        name_of_id = self.get_name_from_id(unique_id)
                        type_of_id = self.get_type_from_id(unique_id)

                        logger.debug("======[ DEVICE INFOS ]======")
                        logger.debug("ID {}".format(device_id))
                        logger.debug("ENDPOINT ID {}".format(endpoint_id))
                        logger.debug("Name {}".format(name_of_id))
                        logger.debug("Type {}".format(type_of_id))
                        logger.debug("==========================")

                        for elem in endpoint["cdata"]:
                            device_class_of_id = None
                            state_class_of_id = None
                            unit_of_measurement_of_id = None
                            elementName = None
                            elementIndex = None

                    except Exception as e:
                        logger.error('msg_cdata error in parsing !')
                        logger.error(e)


    async def parse_devices_data(self, parsed):
        for i in parsed:
            for endpoint in i["endpoints"]:
                if endpoint["error"] == 0 and len(endpoint["data"]) > 0:
                    try:
                        attr_alarm = {}
                        device_id = i["id"]
                        endpoint_id = endpoint["id"]
                        unique_id = str(endpoint_id) + "_" + str(device_id)
                        name_of_id = self.get_name_from_id(unique_id)
                        type_of_id = self.get_type_from_id(unique_id)

                        logger.debug("======[ DEVICE INFOS ]======")
                        logger.debug("ID {}".format(device_id))
                        logger.debug("ENDPOINT ID {}".format(endpoint_id))
                        logger.debug("Name {}".format(name_of_id))
                        logger.debug("Type {}".format(type_of_id))
                        logger.debug("==========================")

                        for elem in endpoint["data"]:
                            logger.debug("CURRENT ELEM={}".format(elem))
                            # endpoint_id = None

                            # Element name
                            elementName = elem["name"]
                            # Element value
                            elementValue = elem["value"]
                            elementValidity = elem["validity"]
                            #print_id = None
                            #if len(name_of_id) != 0:
                            #    print_id = name_of_id
                            #    endpoint_id = device_endpoint[device_id]
                            #else:
                            #    print_id = device_id
                            #    endpoint_id = device_endpoint[device_id]

                            if type_of_id == 'alarm':
                                if elementName in deviceAlarmKeywords and elementValidity == 'upToDate':
                                    attr_alarm['device_id'] = device_id
                                    attr_alarm['endpoint_id'] = endpoint_id
                                    attr_alarm['id'] = str(
                                        device_id) + '_' + str(endpoint_id)
                                    attr_alarm['alarm_name'] = "Tyxal Alarm"
                                    attr_alarm['name'] = "Tyxal Alarm"
                                    attr_alarm['device_type'] = 'alarm_control_panel'
                                    attr_alarm[elementName] = elementValue

                    except Exception as e:
                        logger.error('msg_data error in parsing !')
                        logger.error(e)

                    # Get last known state (for alarm) # NEW METHOD
                    if 'device_type' in attr_alarm and attr_alarm['device_type'] == 'alarm_control_panel':
                        logger.debug(attr_alarm)
                        state = None
                        try:
                            # {
                            # "name": "alarmState",
                            # "type": "string",
                            # "permission": "r",
                            # "enum_values": ["OFF", "DELAYED", "ON", "QUIET"]
                            # },
                            # {
                            # "name": "alarmMode",
                            # "type": "string",
                            # "permission": "r",
                            # "enum_values": ["OFF", "ON", "PART", "TEST", "PERI", "MAINTENANCE"]
                            # },
                            # ...
                            # {
                            # "name": "alarmSOS",
                            # "type": "boolean",
                            #  "permission": "r",
                            #  "validity": "ALARM_POLLING",
                            #  "unit": "boolean"
                            # },
                            # ...
                            # {
                            # "name": "part1State",
                            # "type": "string",
                            # "permission": "r",
                            # "validity": "ALARM_POLLING",
                            #  "enum_values": ["UNUSED", "ON", "OFF"]
                            #  },
                            # ...

                            if ('alarmState' in attr_alarm and attr_alarm['alarmState'] == "ON") or (
                                    'alarmState' in attr_alarm and attr_alarm['alarmState']) == "QUIET":
                                state = "triggered"

                            elif 'alarmState' in attr_alarm and attr_alarm['alarmState'] == "DELAYED":
                                state = "pending"

                            if 'alarmSOS' in attr_alarm and attr_alarm['alarmSOS'] == "true":
                                state = "triggered"

                            elif 'alarmMode' in attr_alarm and attr_alarm["alarmMode"] == "ON":
                                state = "armed_away"

                            # armed_night n'est pas correctement géré.
                            # Il faudrait tester atttr['part1State'] et atttr['part2State'] pour distinguer
                            # armed_home et armed-night en fonction de leur zone.
                            # Pour le moment, il faut utiliser uniquement ARM_HOME
                            elif 'alarmMode' in attr_alarm and attr_alarm["alarmMode"] == "PART":
                                state = "armed_home"

                            elif 'alarmMode' in attr_alarm and attr_alarm["alarmMode"] == "OFF":
                                state = "disarmed"

                            elif 'alarmMode' in attr_alarm and attr_alarm["alarmMode"] == "MAINTENANCE":
                                state = "disarmed"

                            if not (state is None):
                                # logger.debug(state)
                                alarm = "alarm_tydom_" + str(endpoint_id)
                                # logger.debug("Alarm created / updated : "+alarm)
                                alarm = Alarm(
                                    current_state=state,
                                    alarm_pin=self.tydom_client.alarm_pin,
                                    tydom_attributes=attr_alarm,
                                    mqtt=self.mqtt_client)
                                await alarm.update()
                            else:
                                # logger.debug(state)
                                alarm = "alarm_tydom_" + str(endpoint_id)
                                # logger.debug("Alarm created / updated : "+alarm)
                                alarm = Alarm(
                                    current_state=None,
                                    alarm_pin=self.tydom_client.alarm_pin,
                                    tydom_attributes=attr_alarm,
                                    mqtt=self.mqtt_client)
                                await alarm.update()

                        except Exception as e:
                            logger.error("Error in alarm parsing !")
                            logger.error(e)
                            pass
                    else:
                        pass


    # PUT response DIRTY parsing
    def parse_put_response(self, bytes_str, start=6):
        # TODO : Find a cooler way to parse nicely the PUT HTTP response
        resp = bytes_str[len(self.cmd_prefix):].decode("utf-8")
        fields = resp.split("\r\n")
        fields = fields[start:]  # ignore the PUT / HTTP/1.1
        end_parsing = False
        i = 0
        output = str()
        while not end_parsing:
            field = fields[i]
            if len(field) == 0 or field == '0':
                end_parsing = True
            else:
                output += field
                i = i + 2
        parsed = json.loads(output)
        return json.dumps(parsed)


    # FUNCTIONS

    def response_from_bytes(self, data):
        sock = BytesIOSocket(data)
        response = HTTPResponse(sock)
        response.begin()
        return urllib3.HTTPResponse.from_httplib(response)


    def put_response_from_bytes(self, data):
        request = HTTPRequest(data)
        return request


    def get_type_from_id(self, id):
        deviceType = ""
        if len(device_type) != 0 and id in device_type.keys():
            deviceType = device_type[id]
        else:
            logger.warn('%s not in dic device_type'.format(id))

        return(deviceType)


    # Get pretty name for a device id
    def get_name_from_id(self, id):
        name = ""
        if len(device_name) != 0 and id in device_name.keys():
            name = device_name[id]
        else:
            logger.warn('%s not in dic device_name'.format(id))
        return name


class BytesIOSocket:
    def __init__(self, content):
        self.handle = BytesIO(content)

    def makefile(self, mode):
        return self.handle


class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        #self.rfile = StringIO(request_text)
        self.raw_requestline = request_text
        self.error_code = self.error_message = None
        self.parse_request()

    def send_error(self, code, message):
        self.error_code = code
        self.error_message = message
