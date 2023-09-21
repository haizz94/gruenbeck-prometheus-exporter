import requests
import math
import base64
import hashlib
import random
import json
import websocket
from threading import Thread
from utils import wait_until

class GruenbeckApi(object):
    def __init__(self, user: str, password: str) -> None:
        self.__ws = websocket.WebSocketApp
        self.__accessToken = str
        self.__refreshToken = str
        self.__deviceId = str
        self.__user = user
        self.__password = password
        self.__userAgent = "ioBroker 41"
        self.__sdVersion = "2020-08-03"
        self.__socketInfoUpdated = False
        self.nextRegeneration = ""
        self.rawWaterHardness = 0.0
        self.softWaterHardness = 0.0
        self.mode = 0
        self.hasError = False
        self.waterUsages = [0.0, 0.0]
        self.regenerationCounter = 0
        self.waterFlows = [0.0, 0.0]
        self.remainingCapacitiesM3 = [0.0, 0.0]
        self.remainingCapacitiesPercent =[0.0, 0.0]
        self.saltRange = 0
        self.saltUsage = 0
        self.maintenanceLeftDays = 0
    def __selectDevice(self) -> bool:
        print("Looking for devices...")
        headers = {
            "Host": "prod-eu-gruenbeck-api.azurewebsites.net",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Gruenbeck/354 CFNetwork/1209 Darwin/20.2.0",
            "Authorization": "Bearer " + self.__accessToken,
            "Accept-Language": "de-de",
            "cache-control": "no-cache"
        }
        url = "https://prod-eu-gruenbeck-api.azurewebsites.net/api/devices?api-version=" + self.__sdVersion
        response = requests.get(url, headers=headers)
        responseJson = json.loads(response.text)
        
        #Filter SoftLIQ devices
        devices = [x for x in responseJson if "softliq" in x['id'].lower()]
        deviceCount = len(devices)
        if deviceCount == 0:
            print("Found no devices")
        else:
            print("Found " + str(deviceCount) + "SoftLIQ devices")
            self.__deviceId = devices[0]["id"]
            print("Using device with ID: " + devices[0]["id"] + " and name: " + devices[0]["name"])
            return True
        return False
    def updateInfos(self):
        endpoint = ""; #Possible endpoints: parameters, measurements/salt, measurements/water
        headers = {
            "Host": "prod-eu-gruenbeck-api.azurewebsites.net",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.__userAgent,
            "Authorization": "Bearer " + self.__accessToken,
            "Accept-Language": "de-de",
            "cache-control": "no-cache",
        }
        url = "https://prod-eu-gruenbeck-api.azurewebsites.net/api/devices/" + self.__deviceId + "/" + endpoint + "?api-version=" + self.__sdVersion
        response = requests.get(url, headers=headers)
        if response.status_code < 400:
            responseJson = json.loads(response.text)
            self.hasError = bool(responseJson["hasError"])
            self.mode = int(responseJson['mode'])
            self.nextRegeneration = responseJson['nextRegeneration']
            self.rawWaterHardness = float(responseJson['rawWater'])
            self.softWaterHardness = float(responseJson['softWater'])
            print("Successfully set mg infos")
            print("try refreshing SD...")
            headers = {
            "Host": "prod-eu-gruenbeck-api.azurewebsites.net",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Gruenbeck/354 CFNetwork/1209 Darwin/20.2.0",
            "Accept-Language": "de-de",
            "Authorization": "Bearer " + self.__accessToken,
            }
            url = "https://prod-eu-gruenbeck-api.azurewebsites.net/api/devices/" + self.__deviceId + "/realtime/refresh?api-version=" + self.__sdVersion
            response = requests.post(url, headers=headers)
            if(response.status_code < 400):
                print("Successfully refreshed SD")
                wait_until(lambda: self.__socketInfoUpdated == True, 5)
                return
        
        print("Error during updating values. Try to relogin...")
        self.__ws.close()
        self.__login()
        self.__connectWebSocket()          
    def __leaveSD(self):
        print("leave SD")
        self.__refreshTimer.cancel()
        headers = {
            "Host": "prod-eu-gruenbeck-api.azurewebsites.net",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Gruenbeck/354 CFNetwork/1209 Darwin/20.2.0",
            "Accept-Language": "de-de",
            "Authorization": "Bearer " + self.__accessToken,
        }
        url = "https://prod-eu-gruenbeck-api.azurewebsites.net/api/devices/" + self.__deviceId + "/realtime/leave?api-version=" + self.__sdVersion
        response = requests.post(url, headers=headers)
        if(response.status_code >= 400):
            print("error leaving SD")
    def init(self):
        self.__login()
        if (len(self.__accessToken) > 0):
            if self.__selectDevice():
                self.__connectWebSocket()

    def __enterSD(self):
        print("try entering SD...")
        self.__socketInfoUpdated = False
        headers = {
            "Host": "prod-eu-gruenbeck-api.azurewebsites.net",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Gruenbeck/354 CFNetwork/1209 Darwin/20.2.0",
            "Accept-Language": "de-de",
            "Authorization": "Bearer " + self.__accessToken,
        }
        
        url = "https://prod-eu-gruenbeck-api.azurewebsites.net/api/devices/" +\
        self.__deviceId + "/realtime/enter?api-version=" + self.__sdVersion
        response = requests.post(url, headers=headers)
        if(response.status_code < 400):
            print("Successfully entered SD")  
        else:
            print("Error during entering SD")        

    def __on_message(self, ws, message):
        try:
            dataSplit = message.split("")
            for dataElement in dataSplit:
                if not dataElement:
                    continue
                messageJson = json.loads(dataElement)
                if "arguments" in messageJson:
                    if len(messageJson["arguments"]) > 0:
                        messageArgs =  messageJson["arguments"][0]
                        print(messageArgs)
                        if "mcountwater1" in messageArgs:
                            self.waterUsages[0] = messageArgs['mcountwater1']
                        if "mcountwater2" in messageArgs:
                            self.waterUsages[1] = messageArgs['mcountwater2']
                        if "mcountreg" in messageArgs:
                            self.regenerationCounter = messageArgs['mcountreg']
                        if "msaltusage" in messageArgs:
                            self.saltUsage = messageArgs['msaltusage']
                        if "msaltrange" in messageArgs:
                            self.saltRange = messageArgs['msaltrange']
                        if "mflow1" in messageArgs:
                            self.waterFlows[0] = messageArgs['mflow1']
                        if "mflow2" in messageArgs:
                            self.waterFlows[1] = messageArgs['mflow2']
                        if "mrescapa1" in messageArgs:
                            self.remainingCapacitiesM3[0] = messageArgs['mrescapa1']
                        if "mrescapa2" in messageArgs:
                            self.remainingCapacitiesM3[1] = messageArgs['mrescapa2']
                        if "mresidcap1" in messageArgs:
                            self.remainingCapacitiesPercent[0] = messageArgs['mresidcap1']
                        if "mresidcap2" in messageArgs:
                            self.remainingCapacitiesPercent[1] = messageArgs['mresidcap2']
        except:
            print("Websocket parse error")
        self.__socketInfoUpdated = True

    @staticmethod
    def __on_error(ws, error):
        print(error)

    def __on_close(self, ws, close_status_code, close_msg):
        print("### closed ###")
        self.__leaveSD()

    def __on_open(self, ws):
        print("Opened connection")
        ws.send('{"protocol":"json","version":1}');
        self.__enterSD()
    
    def __getCodeChallenge(self):
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        hash = ""
        result = ""
        while (len(hash) == 0) or (hash.find("+") != -1) or (hash.find("/") != -1) or (hash.find("=") != -1) or (result.find("+") != -1) or (result.find("/") != -1):     
            result = ""
            for x in reversed(range(0, 64)):
                result += chars[math.floor(random.random() * len(chars))]
            result = base64.b64encode(result.encode('utf-8')).decode('utf-8')
            result = result.replace("=", "")
            hash = base64.b64encode(hashlib.sha256(result.encode('utf-8')).digest()).decode("utf-8")
            hash = hash[0:len(hash) - 1]   
        return [result, hash]   

    def __login(self):
        challenge = self.__getCodeChallenge()
        code_verifier = challenge[0]
        codeChallenge = challenge[1]
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "br, gzip, deflate",
            "Connection": "keep-alive",
            "Accept-Language": "de-de",
            "User-Agent": self.__userAgent
            }
        url = "https://gruenbeckb2c.b2clogin.com/a50d35c1-202f-4da7-aa87-76e51a3098c6/b2c_1a_signinup/oauth2/v2.0/authorize?" +\
            "x-client-Ver=0.8.0&state=NjkyQjZBQTgtQkM1My00ODBDLTn3MkYtOTZCQ0QyQkQ2NEE5&client_info=1&response_type=code&code_challenge_method=S256&x-app-name=Gr%C3%BCnbeck&x-client-OS=14.3&x-app-ver=1.2.1&scope=https%3A%2F%2Fgruenbeckb2c.onmicrosoft.com%2Fiot%2Fuser_impersonation%20openid%20profile%20offline_access&x-client-SKU=MSAL.iOS&" +\
                    "code_challenge=" +\
                    codeChallenge +\
                    "&x-client-CPU=64&client-request-id=F2929DED-2C9D-49F5-A0F4-31215427667C&redirect_uri=msal5a83cc16-ffb1-42e9-9859-9fbf07f36df8%3A%2F%2Fauth&client_id=5a83cc16-ffb1-42e9-9859-9fbf07f36df8&haschrome=1&return-client-request-id=true&x-client-DM=iPhone"
        response = requests.get(url, headers=headers)
        print("Login step 1")
        start = response.text.find("csrf") + 7
        end = response.text.find(",", start) - 1
        csrf = response.text[start:end]
        start = response.text.find("transId") + 10
        end = response.text.find(",", start) - 1
        transId = response.text[start:end]
        start = response.text.find("policy") + 9
        end = response.text.find(",", start) - 1
        policy = response.text[start:end]
        start = response.text.find("tenant") + 9
        end = response.text.find(",", start) - 1
        tenant = response.text[start:end]
        filteredCookies = []
        for c in response.cookies:
            filteredCookies.append(c.name + "=" + c.value)
        cookieString = "; ".join(str(x) for x in filteredCookies)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-CSRF-TOKEN": csrf,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://gruenbeckb2c.b2clogin.com",
            "Cookie": cookieString,
            "User-Agent": self.__userAgent,
        }
        url = "https://gruenbeckb2c.b2clogin.com" + tenant +\
            "/SelfAsserted?tx=" + transId + "&p=" + policy
        postParams = {
            "request_type": "RESPONSE",
            "signInName": self.__user,
            "password": self.__password,
        }
        response = requests.post(url, headers=headers, params=postParams)
        print("Login step 2")
        filteredCookies.clear()
        for c in response.cookies:
            filteredCookies.append(c.name + "=" + c.value)
        cookieString = "; ".join(str(x) for x in filteredCookies)
        cookieString += "; x-ms-cpim-csrf=" + csrf
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "br, gzip, deflate",
            "Connection": "keep-alive",
            "Accept-Language": "de-de",
            "Cookie": cookieString,
            "User-Agent": self.__userAgent,
        }
        url = "https://gruenbeckb2c.b2clogin.com" + tenant +\
            "/api/CombinedSigninAndSignup/confirmed?csrf_token=" + csrf +\
            "&tx=" + transId +\
            "&p=" + policy
        
        response = requests.get(url, headers=headers, allow_redirects=False)

        if response.status_code == 302 and response.text.find("code") != -1:
            start = response.text.find("code%3d") + 7
            end = response.text.find(">here") - 1
            code = response.text[start:end]
            headers = {
                "Host": "gruenbeckb2c.b2clogin.com",
                "x-client-SKU": "MSAL.iOS",
                "Accept": "application/json",
                "x-client-OS": "14.3",
                "x-app-name": "Grünbeck",
                "x-client-CPU": "64",
                "x-app-ver": "1.2.0",
                "Accept-Language": "de-de",
                "client-request-id": "F2929DED-2C9D-49F5-A0F4-31215427667C",
                "x-ms-PkeyAuth": "1.0",
                "x-client-Ver": "0.8.0",
                "x-client-DM": "iPhone",
                "User-Agent": "Gruenbeck/354 CFNetwork/1209 Darwin/20.2.0",
                "return-client-request-id": "true",
            }
            url = "https://gruenbeckb2c.b2clogin.com" + tenant + "/oauth2/v2.0/token"
            postParams = {
                "client_info": "1",
                "scope": "https://gruenbeckb2c.onmicrosoft.com/iot/user_impersonation openid profile offline_access",
                "code": code,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
                "redirect_uri": "msal5a83cc16-ffb1-42e9-9859-9fbf07f36df8://auth",
                "client_id": "5a83cc16-ffb1-42e9-9859-9fbf07f36df8",
            }
            print("Login step 3")
            response = requests.post(url=url, headers=headers, allow_redirects=False, params=postParams)
            responseTokens = json.loads(response.text)
            self.__accessToken = responseTokens["access_token"]
            self.__refreshToken = responseTokens["refresh_token"]
            print("Login successful")
    def __connectWebSocket(self):
        print("connect mg web socket")
        headers = {
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": "file://",
            "Accept": "*/*",
            "User-Agent": "Gruenbeck/354 CFNetwork/1209 Darwin/20.2.0",
            "Authorization": "Bearer " + self.__accessToken,
            "Accept-Language": "de-de",
            "cache-control": "no-cache",
            "X-Requested-With": "XMLHttpRequest",
        }
        url = "https://prod-eu-gruenbeck-api.azurewebsites.net/api/realtime/negotiate"
        response = requests.get(url, headers=headers)
        if(response.status_code >= 400):
            print("error connecting web socket")
            print(response.text)
        else:
            responseJson = json.loads(response.text)
            wsUrl = responseJson["url"]
            wsAccessToken = responseJson["accessToken"]
            headers = {
                "Content-Type": "text/plain;charset=UTF-8",
                "Origin": "file://",
                "Accept": "*/*",
                "User-Agent": "Gruenbeck/354 CFNetwork/1209 Darwin/20.2.0",
                "Authorization": "Bearer " + wsAccessToken,
                "Accept-Language": "de-de",
                "X-Requested-With": "XMLHttpRequest",
            }
            url = "https://prod-eu-gruenbeck-signalr.service.signalr.net/client/negotiate?hub=gruenbeck"
            response = requests.post(url, headers=headers)
            responseJson = json.loads(response.text)
            wsConnectionId = responseJson["connectionId"]
            headers = {
                "Upgrade": "websocket",
                "Host": "prod-eu-gruenbeck-signalr.service.signalr.net",
                "Origin": "null",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
                "User-Agent":
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            }
            url = "wss://prod-eu-gruenbeck-signalr.service.signalr.net/client/?hub=gruenbeck&id=" +\
                wsConnectionId +\
                "&access_token=" +\
                wsAccessToken
            #websocket.enableTrace(True)
            
            self.__ws = websocket.WebSocketApp(url=url,
                #header=headers,
                on_open=self.__on_open,
                on_message=self.__on_message,
                on_error=self.__on_error,
                on_close=self.__on_close)

            Thread(target=self.__ws.run_forever).start()        