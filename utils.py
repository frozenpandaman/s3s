# (ↄ) 2017-2022 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3

import base64, datetime, json, re, sys, uuid
import requests
from bs4 import BeautifulSoup

SPLATNET3_URL = "https://api.lp1.av5ja.srv.nintendo.net"
GRAPHQL_URL   = "https://api.lp1.av5ja.srv.nintendo.net/api/graphql"
FALLBACK_WEB_VIEW_VERSION = "1.0.0-5644e7a2" # fallback for current splatnet 3 ver
S3S_NAMESPACE = uuid.UUID('b3a2dbf5-2c09-4792-b78c-00b548b70aeb')

SUPPORTED_KEYS = [
	"ignore_private",
	"app_user_agent",
	"force_uploads"
]

# SHA256 hash database for SplatNet 3 GraphQL queries
# full list: https://github.com/samuelthomas2774/nxapi/discussions/11#discussioncomment-3737698
translate_rid = {
	'HomeQuery':                       'dba47124d5ec3090c97ba17db5d2f4b3', # blank vars
	'LatestBattleHistoriesQuery':      '7d8b560e31617e981cf7c8aa1ca13a00', # INK / blank vars - query1
	'RegularBattleHistoriesQuery':     'f6e7e0277e03ff14edfef3b41f70cd33', # INK / blank vars - query1
	'BankaraBattleHistoriesQuery':     'c1553ac75de0a3ea497cdbafaa93e95b', # INK / blank vars - query1
	'PrivateBattleHistoriesQuery':     '38e0529de8bc77189504d26c7a14e0b8', # INK / blank vars - query1
	'VsHistoryDetailQuery':            '2b085984f729cd51938fc069ceef784a', # INK / req "vsResultId" - query2
	'CoopHistoryQuery':                '817618ce39bcf5570f52a97d73301b30', # SR  / blank vars - query1
	'CoopHistoryDetailQuery':          'f3799a033f0a7ad4b1b396f9a3bafb1e'  # SR  / req "coopHistoryDetailId" - query2
}

def get_web_view_ver(bhead, gtoken):
	'''Find & parse the SplatNet 3 main.js file for the current site version.'''

	app_head = { # bhead should have all fields from headbutt() & gtoken will be valid
		'Upgrade-Insecure-Requests':   '1',
		'User-Agent':                  bhead["User-Agent"],
		'Accept':                      '*/*',
		'DNT':                         '1',
		'X-AppColorScheme':            'DARK',
		'X-Requested-With':            'com.nintendo.znca',
		'Sec-Fetch-Site':              'none',
		'Sec-Fetch-Mode':              'navigate',
		'Sec-Fetch-User':              '?1',
		'Sec-Fetch-Dest':              'document',
		'Accept-Encoding':             bhead["Accept-Encoding"],
		'Accept-Language':             bhead["Accept-Language"]
	}
	app_cookies = {
		'_gtoken': gtoken, # X-GameWebToken
		'_dnt':    '1'     # Do Not Track
	}
	home = requests.get(SPLATNET3_URL, headers=app_head, cookies=app_cookies)
	if home.status_code != 200:
		return FALLBACK_WEB_VIEW_VERSION

	soup = BeautifulSoup(home.text, "html.parser")
	main_js = soup.select_one("script[src*='static']")

	if not main_js: # failed to parse html for main.js file
		return FALLBACK_WEB_VIEW_VERSION

	main_js_url = SPLATNET3_URL + main_js.attrs["src"]

	app_head = {
		'User-Agent':          bhead["User-Agent"],
		'Accept':              '*/*',
		'X-Requested-With':    'com.nintendo.znca',
		'Sec-Fetch-Site':      'same-origin',
		'Sec-Fetch-Mode':      'no-cors',
		'Sec-Fetch-Dest':      'script',
		'Referer':             bhead["Referer"],
		'Accept-Encoding':     bhead["Accept-Encoding"],
		'Accept-Language':     bhead["Accept-Language"]
	}

	main_js_body = requests.get(main_js_url, headers=app_head, cookies=app_cookies)
	if main_js_body.status_code != 200:
		return FALLBACK_WEB_VIEW_VERSION

	pattern = r"\b(?P<revision>[0-9a-f]{40})\b.*revision_info_not_set\"\),.*?=\"(?P<version>\d+\.\d+\.\d+)"
	match = re.search(pattern, main_js_body.text)
	if match is None:
		return FALLBACK_WEB_VIEW_VERSION

	version, revision = match.group("version"), match.group("revision")
	return f"{version}-{revision[:8]}"


def set_noun(which):
	'''Returns the term to be used when referring to the type of results in question.'''

	if which == "both":
		return "battles/jobs"
	elif which == "salmon":
		return "jobs"
	else: # "ink"
		return "battles"


def b64d(string):
	'''Base64 decode a string and cut off the SplatNet prefix.'''

	thing_id = base64.b64decode(string).decode('utf-8')
	thing_id = thing_id.replace("VsStage-", "")
	thing_id = thing_id.replace("VsMode-", "")
	thing_id = thing_id.replace("CoopStage-", "")
	thing_id = thing_id.replace("CoopGrade-", "")

	if "Weapon-" in thing_id:
		thing_id = thing_id.replace("Weapon-", "")
		if len(thing_id) == 5 and thing_id[:1] == "2" and thing_id[-3:] == "900": # grizzco weapon ID from a hacker
			return ""

	if thing_id[:15] == "VsHistoryDetail" or thing_id[:17] == "CoopHistoryDetail":
		return thing_id # string
	else:
		return int(thing_id) # integer


def epoch_time(time_string):
	'''Converts a playedTime string into an int representing the epoch time.'''

	utc_time = datetime.datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")
	epoch_time = int((utc_time - datetime.datetime(1970, 1, 1)).total_seconds())
	return epoch_time


def gen_graphql_body(sha256hash, varname=None, varvalue=None):
	'''Generates a JSON dictionary, specifying information to retrieve, to send with GraphQL requests.'''
	great_passage = {
		"extensions": {
			"persistedQuery": {
				"sha256Hash": sha256hash,
				"version": 1
			}
		},
		"variables": {}
	}

	if varname is not None and varvalue is not None:
		great_passage["variables"][varname] = varvalue

	return json.dumps(great_passage)


def custom_key_exists(key, config_data, value=True):
	'''Checks if a given custom key exists in config.txt and is set to the specified value (true by default).'''

	# https://github.com/frozenpandaman/s3s/wiki/config-keys
	if key not in SUPPORTED_KEYS:
		print("(!) Checking unexpected custom key")
	return str(config_data.get(key, None)).lower() == str(value).lower()


if __name__ == "__main__":
	print("This program cannot be run alone. See https://github.com/frozenpandaman/s3s")
	sys.exit(0)
