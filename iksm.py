# (ↄ) 2017-2023 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3

import base64, hashlib, json, os, re, sys, urllib
import requests
from bs4 import BeautifulSoup

USE_OLD_NSOAPP_VER    = False # Change this to True if you're getting a "9403: Invalid token." error

S3S_VERSION           = "unknown"
NSOAPP_VERSION        = "unknown"
NSOAPP_VER_FALLBACK   = "2.5.0"
WEB_VIEW_VERSION      = "unknown"
WEB_VIEW_VER_FALLBACK = "3.0.0-2857bc50" # fallback for current splatnet 3 ver
SPLATNET3_URL         = "https://api.lp1.av5ja.srv.nintendo.net"

# functions in this file & call stack:
# - get_nsoapp_version()
# - get_web_view_ver()
# - log_in() -> get_session_token()
# - get_gtoken() -> call_f_api()
# - get_bullet()
# - enter_tokens()

session = requests.Session()

def get_nsoapp_version():
	'''Fetches the current Nintendo Switch Online app version from the Apple App Store and sets it globally.'''

	if USE_OLD_NSOAPP_VER:
		return NSOAPP_VER_FALLBACK

	global NSOAPP_VERSION
	if NSOAPP_VERSION != "unknown": # already set
		return NSOAPP_VERSION
	else:
		try:
			page = requests.get("https://apps.apple.com/us/app/nintendo-switch-online/id1234806557")
			soup = BeautifulSoup(page.text, 'html.parser')
			elt = soup.find("p", {"class": "whats-new__latest__version"})
			ver = elt.get_text().replace("Version ", "").strip()

			NSOAPP_VERSION = ver

			return NSOAPP_VERSION
		except: # error with web request
			return NSOAPP_VER_FALLBACK


def get_web_view_ver(bhead=[], gtoken=""):
	'''Finds & parses the SplatNet 3 main.js file to fetch the current site version and sets it globally.'''

	global WEB_VIEW_VERSION
	if WEB_VIEW_VERSION != "unknown":
		return WEB_VIEW_VERSION
	else:
		app_head = {
			'Upgrade-Insecure-Requests':   '1',
			'Accept':                      '*/*',
			'DNT':                         '1',
			'X-AppColorScheme':            'DARK',
			'X-Requested-With':            'com.nintendo.znca',
			'Sec-Fetch-Site':              'none',
			'Sec-Fetch-Mode':              'navigate',
			'Sec-Fetch-User':              '?1',
			'Sec-Fetch-Dest':              'document'
		}
		app_cookies = {
			'_dnt':    '1'     # Do Not Track
		}

		if bhead:
			app_head["User-Agent"]      = bhead.get("User-Agent")
			app_head["Accept-Encoding"] = bhead.get("Accept-Encoding")
			app_head["Accept-Language"] = bhead.get("Accept-Language")
		if gtoken:
			app_cookies["_gtoken"] = gtoken # X-GameWebToken

		home = requests.get(SPLATNET3_URL, headers=app_head, cookies=app_cookies)
		if home.status_code != 200:
			return WEB_VIEW_VER_FALLBACK

		soup = BeautifulSoup(home.text, "html.parser")
		main_js = soup.select_one("script[src*='static']")

		if not main_js: # failed to parse html for main.js file
			return WEB_VIEW_VER_FALLBACK

		main_js_url = SPLATNET3_URL + main_js.attrs["src"]

		app_head = {
			'Accept':              '*/*',
			'X-Requested-With':    'com.nintendo.znca',
			'Sec-Fetch-Site':      'same-origin',
			'Sec-Fetch-Mode':      'no-cors',
			'Sec-Fetch-Dest':      'script',
			'Referer':             SPLATNET3_URL # sending w/o lang, na_country, na_lang params
		}
		if bhead:
			app_head["User-Agent"]      = bhead.get("User-Agent")
			app_head["Accept-Encoding"] = bhead.get("Accept-Encoding")
			app_head["Accept-Language"] = bhead.get("Accept-Language")

		main_js_body = requests.get(main_js_url, headers=app_head, cookies=app_cookies)
		if main_js_body.status_code != 200:
			return WEB_VIEW_VER_FALLBACK

		pattern = r"\b(?P<revision>[0-9a-f]{40})\b[\S]*?void 0[\S]*?\"revision_info_not_set\"\}`,.*?=`(?P<version>\d+\.\d+\.\d+)-"
		match = re.search(pattern, main_js_body.text)
		if match is None:
			return WEB_VIEW_VER_FALLBACK

		version, revision = match.group("version"), match.group("revision")
		ver_string = f"{version}-{revision[:8]}"

		WEB_VIEW_VERSION = ver_string

		return WEB_VIEW_VERSION


def log_in(ver, app_user_agent):
	'''Logs in to a Nintendo Account and returns a session_token.'''

	global S3S_VERSION
	S3S_VERSION = ver

	auth_state = base64.urlsafe_b64encode(os.urandom(36))

	auth_code_verifier = base64.urlsafe_b64encode(os.urandom(32))
	auth_cv_hash = hashlib.sha256()
	auth_cv_hash.update(auth_code_verifier.replace(b"=", b""))
	auth_code_challenge = base64.urlsafe_b64encode(auth_cv_hash.digest())

	app_head = {
		'Host':                      'accounts.nintendo.com',
		'Connection':                'keep-alive',
		'Cache-Control':             'max-age=0',
		'Upgrade-Insecure-Requests': '1',
		'User-Agent':                app_user_agent,
		'Accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8n',
		'DNT':                       '1',
		'Accept-Encoding':           'gzip,deflate,br',
	}

	body = {
		'state':                               auth_state,
		'redirect_uri':                        'npf71b963c1b7b6d119://auth',
		'client_id':                           '71b963c1b7b6d119',
		'scope':                               'openid user user.birthday user.mii user.screenName',
		'response_type':                       'session_token_code',
		'session_token_code_challenge':        auth_code_challenge.replace(b"=", b""),
		'session_token_code_challenge_method': 'S256',
		'theme':                               'login_form'
	}

	print("\nMake sure you have read the \"Token generation\" section of the readme before proceeding. To manually input your tokens instead, enter \"skip\" at the prompt below.")
	print("\nNavigate to this URL in your browser:")
	print(f'https://accounts.nintendo.com/connect/1.0.0/authorize?{urllib.parse.urlencode(body)}')

	print("Log in, right click the \"Select this account\" button, copy the link address, and paste it below:")
	while True:
		try:
			use_account_url = input("")
			if use_account_url == "skip":
				return "skip"
			session_token_code = re.search('de=(.*)&', use_account_url)
			return get_session_token(session_token_code.group(1), auth_code_verifier)
		except KeyboardInterrupt:
			print("\nBye!")
			sys.exit(1)
		except AttributeError:
			print("Malformed URL. Please try again, or press Ctrl+C to exit.")
			print("URL:", end=' ')
		except KeyError: # session_token not found
			print("\nThe URL has expired. Please log out and back into your Nintendo Account and try again.")
			sys.exit(1)


def get_session_token(session_token_code, auth_code_verifier):
	'''Helper function for log_in().'''

	nsoapp_version = get_nsoapp_version()

	app_head = {
		'User-Agent':      f'OnlineLounge/{nsoapp_version} NASDKAPI Android',
		'Accept-Language': 'en-US',
		'Accept':          'application/json',
		'Content-Type':    'application/x-www-form-urlencoded',
		'Content-Length':  '540',
		'Host':            'accounts.nintendo.com',
		'Connection':      'Keep-Alive',
		'Accept-Encoding': 'gzip'
	}

	body = {
		'client_id':                   '71b963c1b7b6d119',
		'session_token_code':          session_token_code,
		'session_token_code_verifier': auth_code_verifier.replace(b"=", b"")
	}

	url = 'https://accounts.nintendo.com/connect/1.0.0/api/session_token'

	r = session.post(url, headers=app_head, data=body)
	return json.loads(r.text)["session_token"]


def get_gtoken(f_gen_url, session_token, ver):
	'''Provided the session_token, returns a GameWebToken JWT and account info.'''

	nsoapp_version = get_nsoapp_version()

	global S3S_VERSION
	S3S_VERSION = ver

	app_head = {
		'Host':            'accounts.nintendo.com',
		'Accept-Encoding': 'gzip',
		'Content-Type':    'application/json',
		'Content-Length':  '436',
		'Accept':          'application/json',
		'Connection':      'Keep-Alive',
		'User-Agent':      'Dalvik/2.1.0 (Linux; U; Android 7.1.2)'
	}

	body = {
		'client_id':     '71b963c1b7b6d119',
		'session_token': session_token,
		'grant_type':    'urn:ietf:params:oauth:grant-type:jwt-bearer-session-token'
	}

	url = "https://accounts.nintendo.com/connect/1.0.0/api/token"
	r = requests.post(url, headers=app_head, json=body)
	id_response = json.loads(r.text)

	# get user info
	try:
		app_head = {
			'User-Agent':      'NASDKAPI; Android',
			'Content-Type':    'application/json',
			'Accept':          'application/json',
			'Authorization':   f'Bearer {id_response["access_token"]}',
			'Host':            'api.accounts.nintendo.com',
			'Connection':      'Keep-Alive',
			'Accept-Encoding': 'gzip'
		}
	except:
		print("Not a valid authorization request. Please delete config.txt and try again.")
		print("Error from Nintendo (in api/token step):")
		print(json.dumps(id_response, indent=2))
		sys.exit(1)

	url = "https://api.accounts.nintendo.com/2.0.0/users/me"
	r = requests.get(url, headers=app_head)
	user_info = json.loads(r.text)

	user_nickname = user_info["nickname"]
	user_lang     = user_info["language"]
	user_country  = user_info["country"]

	# get access token
	body = {}
	try:
		id_token = id_response["id_token"]
		f, uuid, timestamp = call_f_api(id_token, 1, f_gen_url)

		parameter = {
			'f':          f,
			'language':   user_lang,
			'naBirthday': user_info["birthday"],
			'naCountry':  user_country,
			'naIdToken':  id_token,
			'requestId':  uuid,
			'timestamp':  timestamp
		}
	except SystemExit:
		sys.exit(1)
	except:
		print("Error(s) from Nintendo:")
		print(json.dumps(id_response, indent=2))
		print(json.dumps(user_info, indent=2))
		sys.exit(1)
	body["parameter"] = parameter

	app_head = {
		'X-Platform':       'Android',
		'X-ProductVersion': nsoapp_version,
		'Content-Type':     'application/json; charset=utf-8',
		'Content-Length':   str(990 + len(f)),
		'Connection':       'Keep-Alive',
		'Accept-Encoding':  'gzip',
		'User-Agent':       f'com.nintendo.znca/{nsoapp_version}(Android/7.1.2)',
	}

	url = "https://api-lp1.znc.srv.nintendo.net/v3/Account/Login"
	r = requests.post(url, headers=app_head, json=body)
	splatoon_token = json.loads(r.text)

	try:
		id_token = splatoon_token["result"]["webApiServerCredential"]["accessToken"]
	except:
		# retry once if 9403/9599 error from nintendo
		try:
			f, uuid, timestamp = call_f_api(id_token, 1, f_gen_url)
			body["parameter"]["f"]         = f
			body["parameter"]["requestId"] = uuid
			body["parameter"]["timestamp"] = timestamp
			app_head["Content-Length"]     = str(990 + len(f))
			url = "https://api-lp1.znc.srv.nintendo.net/v3/Account/Login"
			r = requests.post(url, headers=app_head, json=body)
			splatoon_token = json.loads(r.text)
			id_token = splatoon_token["result"]["webApiServerCredential"]["accessToken"]
		except:
			print("Error from Nintendo (in Account/Login step):")
			print(json.dumps(splatoon_token, indent=2))
			print("Try re-running the script. Or, if the NSO app has recently been updated, you may temporarily change `USE_OLD_NSOAPP_VER` to True at the top of iksm.py for a workaround.")
			sys.exit(1)

		f, uuid, timestamp = call_f_api(id_token, 2, f_gen_url)

	# get web service token
	app_head = {
		'X-Platform':       'Android',
		'X-ProductVersion': nsoapp_version,
		'Authorization':    f'Bearer {id_token}',
		'Content-Type':     'application/json; charset=utf-8',
		'Content-Length':   '391',
		'Accept-Encoding':  'gzip',
		'User-Agent':       f'com.nintendo.znca/{nsoapp_version}(Android/7.1.2)'
	}

	body = {}
	parameter = {
		'f':                 f,
		'id':                4834290508791808,
		'registrationToken': id_token,
		'requestId':         uuid,
		'timestamp':         timestamp
	}
	body["parameter"] = parameter

	url = "https://api-lp1.znc.srv.nintendo.net/v2/Game/GetWebServiceToken"
	r = requests.post(url, headers=app_head, json=body)
	web_service_resp = json.loads(r.text)

	try:
		web_service_token = web_service_resp["result"]["accessToken"]
	except:
		# retry once if 9403/9599 error from nintendo
		try:
			f, uuid, timestamp = call_f_api(id_token, 2, f_gen_url)
			body["parameter"]["f"]         = f
			body["parameter"]["requestId"] = uuid
			body["parameter"]["timestamp"] = timestamp
			url = "https://api-lp1.znc.srv.nintendo.net/v2/Game/GetWebServiceToken"
			r = requests.post(url, headers=app_head, json=body)
			web_service_resp = json.loads(r.text)
			web_service_token = web_service_resp["result"]["accessToken"]
		except:
			print("Error from Nintendo (in Game/GetWebServiceToken step):")
			print(json.dumps(web_service_resp, indent=2))
			sys.exit(1)

	return web_service_token, user_nickname, user_lang, user_country


def get_bullet(web_service_token, app_user_agent, user_lang, user_country):
	'''Given a gtoken, returns a bulletToken.'''

	app_head = {
		'Content-Length':   '0',
		'Content-Type':     'application/json',
		'Accept-Language':  user_lang,
		'User-Agent':       app_user_agent,
		'X-Web-View-Ver':   get_web_view_ver(),
		'X-NACOUNTRY':      user_country,
		'Accept':           '*/*',
		'Origin':           SPLATNET3_URL,
		'X-Requested-With': 'com.nintendo.znca'
	}
	app_cookies = {
		'_gtoken': web_service_token, # X-GameWebToken
		'_dnt':    '1'                # Do Not Track
	}
	url = f'{SPLATNET3_URL}/api/bullet_tokens'
	r = requests.post(url, headers=app_head, cookies=app_cookies)

	if r.status_code == 401:
		print("Unauthorized error (ERROR_INVALID_GAME_WEB_TOKEN). Cannot fetch tokens at this time.")
		sys.exit(1)
	elif r.status_code == 403:
		print("Forbidden error (ERROR_OBSOLETE_VERSION). Cannot fetch tokens at this time.")
		sys.exit(1)
	elif r.status_code == 204: # No Content, USER_NOT_REGISTERED
		print("Cannot access SplatNet 3 without having played online.")
		sys.exit(1)

	try:
		bullet_resp = json.loads(r.text)
		bullet_token = bullet_resp["bulletToken"]
	except (json.decoder.JSONDecodeError, TypeError):
		print("Got non-JSON response from Nintendo (in api/bullet_tokens step):")
		print(r.text)
		bullet_token = ""
	except:
		print("Error from Nintendo (in api/bullet_tokens step):")
		print(json.dumps(bullet_resp, indent=2))
		sys.exit(1)

	return bullet_token


def call_f_api(id_token, step, f_gen_url):
	'''Passes an naIdToken to the f generation API (default: imink) & fetches the response (f token, UUID, and timestamp).'''

	try:
		api_head = {
			'User-Agent':   f's3s/{S3S_VERSION}',
			'Content-Type': 'application/json; charset=utf-8'
		}
		api_body = {
			'token':       id_token,
			'hash_method':  step
		}
		api_response = requests.post(f_gen_url, data=json.dumps(api_body), headers=api_head)
		resp = json.loads(api_response.text)

		f = resp["f"]
		uuid = resp["request_id"]
		timestamp = resp["timestamp"]
		return f, uuid, timestamp
	except:
		try: # if api_response never gets set
			if api_response.text:
				print(f"Error during f generation:\n{json.dumps(json.loads(api_response.text), indent=2, ensure_ascii=False)}")
			else:
				print(f"Error during f generation: Error {api_response.status_code}.")
		except:
			print(f"Couldn't connect to f generation API ({f_gen_url}). Please try again.")

		sys.exit(1)


def enter_tokens():
	'''Prompts the user to enter a gtoken and bulletToken.'''

	print("Go to the page below to find instructions to obtain your gtoken and bulletToken:")
	print("https://github.com/frozenpandaman/s3s/wiki/mitmproxy-instructions\n")

	new_gtoken = input("Enter your gtoken: ")
	while len(new_gtoken) != 926:
		new_gtoken = input("Invalid token - length should be 926 characters. Try again.\nEnter your gtoken: ")

	new_bullettoken = input("Enter your bulletToken: ")
	while len(new_bullettoken) != 124:
		if len(new_bullettoken) == 123 and new_bullettoken[-1] != "=":
			new_bullettoken += "=" # add a = to the end, which was probably left off (even though it works without)
		else:
			new_bullettoken = input("Invalid token - length should be 124 characters. Try again.\nEnter your bulletToken: ")

	return new_gtoken, new_bullettoken


if __name__ == "__main__":
	print("This program cannot be run alone. See https://github.com/frozenpandaman/s3s")
	sys.exit(0)
