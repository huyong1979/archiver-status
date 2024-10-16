#!/usr/bin/env python
import threading
import time
import requests
import json
import pprint

from pcaspy import Driver, SimpleServer, Alarm, Severity
from requests.exceptions import Timeout
from requests.exceptions import ConnectionError

# Try the Customized Configuration first, then the default Configuration
try:
    from customized_config import *
except ImportError:
    print('*** No customized_config.py is provided so the default configuration is used ***')
    appliances = [ {'url': 'http://localhost:17665', 'identity': 'appliance0' } ]
    REQUEST_TIMEOUT = 5
    REQUEST_INTERVAL = 5
    prefix = 'MTEST:'

print('\n')
print('*** This tool is used to monitor status of Archiver Appliance deployed as either single node or cluster ***')
print('\n')

number_of_nodes = len(appliances)

if number_of_nodes == 0:
    print('Error: the length of appliances should not be 0, exiting ...')
    exit()

if number_of_nodes == 1:
    print('Configured to monitor single node of Archiver Appliance')
    print(f'url: {appliances[0]["url"]}')
    print(f'identity: {appliances[0]["identity"]}')

if number_of_nodes >= 2:
    print('Configured to monitor multiple nodes of Archiver Appliance cluster')
    print('\n')
    print('All nodes in the cluster are as below')
    for appliance in appliances:
        pprint.pprint(appliance)
    print('\n')

# Build PVs for Archiver Appliance status
pvdb = {}

for appliance in appliances:

    # PVs for single node do not distinguish identifiers, whereas PVs for multiple nodes distinguish identifiers
    pv_identity = '' if number_of_nodes == 1 else appliance['identity']
    pv_separator = '' if number_of_nodes == 1 else ':'

    # Each appliance has the following PVs
    pvdb[f'{pv_identity}{pv_separator}status']                      = { 'type': 'string', 'value': '' }
    pvdb[f'{pv_identity}{pv_separator}MGMT_uptime']                 = { 'type': 'string', 'value': '' }
    pvdb[f'{pv_identity}{pv_separator}pvCount']                     = { 'type': 'int', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}connectedPVCount']            = { 'type': 'int', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}disconnectedPVCount']         = { 'type': 'int', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}pausedPVCount']               = { 'type': 'int', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}dataRateGBPerDay']            = { 'type': 'float', 'prec': 2, 'unit': 'GB/day', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}sts_total_space']             = { 'type': 'float', 'prec': 2, 'unit': 'GB', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}sts_available_space']         = { 'type': 'float', 'prec': 2, 'unit': 'GB', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}sts_available_space_percent'] = { 'type': 'float', 'prec': 2, 'unit': '%', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}mts_total_space']             = { 'type': 'float', 'prec': 2, 'unit': 'GB', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}mts_available_space']         = { 'type': 'float', 'prec': 2, 'unit': 'GB', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}mts_available_space_percent'] = { 'type': 'float', 'prec': 2, 'unit': '%', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}lts_total_space']             = { 'type': 'float', 'prec': 2, 'unit': 'GB', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}lts_available_space']         = { 'type': 'float', 'prec': 2, 'unit': 'GB', 'value': 0 }
    pvdb[f'{pv_identity}{pv_separator}lts_available_space_percent'] = { 'type': 'float', 'prec': 2, 'unit': '%', 'value': 0 }

print('\n')
print('*** The following PVs will be generated ***')
for key, value in pvdb.items():
    print(f'{prefix}{key}')
print('\n')
 
class myDriver(Driver):
    def __init__(self):
        Driver.__init__(self)
        # Create three polling threads for each appliance
        for appliance in appliances:
            self.tid = threading.Thread(target = self.pollInstanceMetrics, args = (appliance,)) 
            self.tid.daemon = True
            self.tid.start()
            self.tid = threading.Thread(target = self.pollApplianceMetrics, args = (appliance,)) 
            self.tid.daemon = True
            self.tid.start()
            self.tid = threading.Thread(target = self.pollStorageMetrics, args = (appliance,)) 
            self.tid.daemon = True
            self.tid.start()

    # Set alarm and invalid value for instance metrics
    def invalidateInstanceMetrics(self, appliance):
        pv_identity = '' if number_of_nodes == 1 else appliance['identity']
        pv_separator = '' if number_of_nodes == 1 else ':'
        self.setParam(f'{pv_identity}{pv_separator}status', 'Disconnected')
        self.setParam(f'{pv_identity}{pv_separator}MGMT_uptime', 'Unknown')
        self.setParam(f'{pv_identity}{pv_separator}pvCount', 0)
        self.setParam(f'{pv_identity}{pv_separator}connectedPVCount', 0)
        self.setParam(f'{pv_identity}{pv_separator}disconnectedPVCount', 0)
        self.setParam(f'{pv_identity}{pv_separator}dataRateGBPerDay', 0)
        self.setParamStatus(f'{pv_identity}{pv_separator}status', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}MGMT_uptime', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}pvCount', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}connectedPVCount', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}disconnectedPVCount', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}dataRateGBPerDay', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.updatePVs()

    # Set alarm and invalid value for appliance metrics
    def invalidateApplianceMetrics(self, appliance):
        pv_identity = '' if number_of_nodes == 1 else appliance['identity']
        pv_separator = '' if number_of_nodes == 1 else ':'
        self.setParam(f'{pv_identity}{pv_separator}pausedPVCount', 0)
        self.setParamStatus(f'{pv_identity}{pv_separator}pausedPVCount', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.updatePVs()

    # Set alarm and invalid value for storage metrics
    def invalidateStorageMetrics(self, appliance):
        pv_identity = '' if number_of_nodes == 1 else appliance['identity']
        pv_separator = '' if number_of_nodes == 1 else ':'
        self.setParam(f'{pv_identity}{pv_separator}sts_total_space', 0)
        self.setParam(f'{pv_identity}{pv_separator}sts_available_space', 0)
        self.setParam(f'{pv_identity}{pv_separator}sts_available_space_percent', 0)
        self.setParam(f'{pv_identity}{pv_separator}mts_total_space', 0)
        self.setParam(f'{pv_identity}{pv_separator}mts_available_space', 0)
        self.setParam(f'{pv_identity}{pv_separator}mts_available_space_percent', 0)
        self.setParam(f'{pv_identity}{pv_separator}lts_total_space', 0)
        self.setParam(f'{pv_identity}{pv_separator}lts_available_space', 0)
        self.setParam(f'{pv_identity}{pv_separator}lts_available_space_percent', 0)
        self.setParamStatus(f'{pv_identity}{pv_separator}sts_total_space', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}sts_available_space', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}sts_available_space_percent', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}mts_total_space', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}mts_available_space', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}mts_available_space_percent', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}lts_total_space', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}lts_available_space', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.setParamStatus(f'{pv_identity}{pv_separator}lts_available_space_percent', Alarm.COMM_ALARM, Severity.MINOR_ALARM)
        self.updatePVs()

    # Polling thread for instance metrics
    def pollInstanceMetrics(self, appliance):
        url = appliance["url"]
        identity = appliance["identity"]
        GET_INSTANCE_METRICS_URL = f'{url}/mgmt/bpl/getInstanceMetrics'

        while True:
            try:
                # Get instance metrics data
                response = requests.get(GET_INSTANCE_METRICS_URL, timeout = REQUEST_TIMEOUT)

                if response.status_code < 200 or response.status_code >= 300:
                    print('Appliance ' + identity + ': ' + 'Bad response status code ' + str(response.status_code) + ' for instance metrics data')
                    self.invalidateInstanceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                text = response.text
                dataList = json.loads(text)

                found = False
                for item in dataList:
                    if 'instance' in item and item['instance'] == identity:
                        data = item
                        found = True
                        break
                
                if not found:
                    print(f'Appliance {identity}: Instance data is not found')
                    self.invalidateInstanceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                if not('status' in data):
                    print(f'Appliance {identity}: Instance metrics data does not include status')
                    self.invalidateInstanceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                if not('MGMT_uptime' in data):
                    print(f'Appliance {identity}: Instance metrics data does not include MGMT_uptime')
                    self.invalidateInstanceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                if not('pvCount' in data):
                    print(f'Appliance {identity}: Instance metrics data does not include pvCount')
                    self.invalidateInstanceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                if not('connectedPVCount' in data):
                    print(f'Appliance {identity}: Instance metrics data does not include connectedPVCount')
                    self.invalidateInstanceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                if not('disconnectedPVCount' in data):
                    print(f'Appliance {identity}: Instance metrics data does not include disconnectedPVCount')
                    self.invalidateInstanceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                status = data['status']  # string
                MGMT_uptime = data['MGMT_uptime']  # string
                pvCount = int(data['pvCount'])  # int
                connectedPVCount = int(data['connectedPVCount'])  # int
                disconnectedPVCount = int(data['disconnectedPVCount'])  # int
                dataRateGBPerDay = float(data['dataRateGBPerDay'])  # float

                # print(status)
                # print(MGMT_uptime)
                # print(pvCount)
                # print(connectedPVCount)
                # print(disconnectedPVCount)
                # print(dataRateGBPerDay)

                pv_identity = '' if number_of_nodes == 1 else appliance['identity']
                pv_separator = '' if number_of_nodes == 1 else ':'
                self.setParam(f'{pv_identity}{pv_separator}status', status)
                self.setParam(f'{pv_identity}{pv_separator}MGMT_uptime', MGMT_uptime)
                self.setParam(f'{pv_identity}{pv_separator}pvCount', pvCount)
                self.setParam(f'{pv_identity}{pv_separator}connectedPVCount', connectedPVCount)
                self.setParam(f'{pv_identity}{pv_separator}disconnectedPVCount', disconnectedPVCount)
                self.setParam(f'{pv_identity}{pv_separator}dataRateGBPerDay', dataRateGBPerDay)

                # do updates so clients see the changes
                self.updatePVs()

            except Timeout:
                print(f'Appliance {identity}: Request for instance metrics data has timed out')
                self.invalidateInstanceMetrics(appliance)

            except ConnectionError:
                print(f'Appliance {identity}: Connection for instance metrics data has been refused')
                self.invalidateInstanceMetrics(appliance)

            # Delay 5 seconds
            time.sleep(REQUEST_INTERVAL)

    # Polling thread for appliance metrics
    def pollApplianceMetrics(self, appliance):
        url = appliance["url"]
        identity = appliance["identity"]
        GET_APPLIANCE_METRICS_FOR_APPLIANCE_URL = f'{url}/mgmt/bpl/getApplianceMetricsForAppliance?appliance={identity}'

        while True:
            try: 
                # Get storage metrics data
                response = requests.get(GET_APPLIANCE_METRICS_FOR_APPLIANCE_URL, timeout = REQUEST_TIMEOUT)

                if response.status_code < 200 or response.status_code >= 300:
                    print('Appliance ' + identity + ': ' + 'Bad response status code ' + str(response.status_code) + ' for appliance metrics data')
                    self.invalidateApplianceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                text = response.text

                if not text:
                    print('Appliance ' + identity + ': ' + 'response text for appliance metrics data is empty, maybe identity is not correct')
                    self.invalidateApplianceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                data = json.loads(text)

                if len(data) == 0:
                    print(f'Appliance {identity}: Empty text response for appliance metrics data')
                    self.invalidateApplianceMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                for item in data:
                    if item['name'] == 'Paused PV count':
                        pausedPVCount = int(item['value'])

                # print(pausedPVCount)

                pv_identity = '' if number_of_nodes == 1 else appliance['identity']
                pv_separator = '' if number_of_nodes == 1 else ':'   
                self.setParam(f'{pv_identity}{pv_separator}pausedPVCount', pausedPVCount)
            
                # do updates so clients see the changes
                self.updatePVs()

            except Timeout:
                print(f'Appliance {identity}: Request for appliance metrics data has timed out')
                self.invalidateApplianceMetrics(appliance)
                
            except ConnectionError:
                print(f'Appliance {identity}: Connection for appliance metrics data has been refused')
                self.invalidateApplianceMetrics(appliance)

            # Delay 5 seconds
            time.sleep(REQUEST_INTERVAL)

    # Polling thread for storage metrics
    def pollStorageMetrics(self, appliance):
        url = appliance["url"]
        identity = appliance["identity"]
        GET_STORAGE_METRICS_FOR_APPLIANCE_URL = f'{url}/mgmt/bpl/getStorageMetricsForAppliance?appliance={identity}'

        while True:
            try: 
                # Get storage metrics data
                response = requests.get(GET_STORAGE_METRICS_FOR_APPLIANCE_URL, timeout = REQUEST_TIMEOUT)

                if response.status_code < 200 or response.status_code >= 300:
                    print('Appliance ' + identity + ': ' + 'Bad response status code ' + str(response.status_code) + ' for storage metrics data')
                    self.invalidateStorageMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                text = response.text

                if not text:
                    print('Appliance ' + identity + ': ' + 'response text for storage metrics data is empty, maybe identity is not correct')
                    self.invalidateStorageMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                data = json.loads(text)

                if len(data) == 0:
                    print(f'Appliance {identity}: Empty text response for storage metrics data')
                    self.invalidateStorageMetrics(appliance)
                    time.sleep(REQUEST_INTERVAL)
                    continue

                for item in data:
                    if item['name'] == 'STS':
                        sts_total_space = float(item['total_space'].replace(',', ''))
                        sts_available_space = float(item['available_space'].replace(',', ''))
                        sts_available_space_percent = float(item['available_space_percent'].replace(',', ''))
                    if item['name'] == 'MTS':
                        mts_total_space = float(item['total_space'].replace(',', ''))
                        mts_available_space = float(item['available_space'].replace(',', ''))
                        mts_available_space_percent = float(item['available_space_percent'].replace(',', ''))
                    if item['name'] == 'LTS':
                        lts_total_space = float(item['total_space'].replace(',', ''))
                        lts_available_space = float(item['available_space'].replace(',', ''))
                        lts_available_space_percent = float(item['available_space_percent'].replace(',', ''))

                # print(sts_total_space)
                # print(sts_available_space)
                # print(sts_available_space_percent)
                # print(mts_total_space)
                # print(mts_available_space)
                # print(mts_available_space_percent)
                # print(lts_total_space)
                # print(lts_available_space)
                # print(lts_available_space_percent)
                        
                pv_identity = '' if number_of_nodes == 1 else appliance['identity']
                pv_separator = '' if number_of_nodes == 1 else ':'
                self.setParam(f'{pv_identity}{pv_separator}sts_total_space', sts_total_space)
                self.setParam(f'{pv_identity}{pv_separator}sts_available_space', sts_available_space)
                self.setParam(f'{pv_identity}{pv_separator}sts_available_space_percent', sts_available_space_percent)
                self.setParam(f'{pv_identity}{pv_separator}mts_total_space', mts_total_space)
                self.setParam(f'{pv_identity}{pv_separator}mts_available_space', mts_available_space)
                self.setParam(f'{pv_identity}{pv_separator}mts_available_space_percent', mts_available_space_percent)
                self.setParam(f'{pv_identity}{pv_separator}lts_total_space', lts_total_space)
                self.setParam(f'{pv_identity}{pv_separator}lts_available_space', lts_available_space)
                self.setParam(f'{pv_identity}{pv_separator}lts_available_space_percent', lts_available_space_percent)
            
                # do updates so clients see the changes
                self.updatePVs()

            except Timeout:
                print(f'Appliance {identity}: Request for storage metrics data has timed out')
                self.invalidateStorageMetrics(appliance)
                
            except ConnectionError:
                print(f'Appliance {identity}: Connection for storage metrics data has been refused')
                self.invalidateStorageMetrics(appliance)

            # Delay 5 seconds
            time.sleep(REQUEST_INTERVAL)

if __name__ == '__main__':
    server = SimpleServer()
    server.createPV(prefix, pvdb)
    driver = myDriver()

    # process CA transactions
    while True:
        server.process(0.1)
