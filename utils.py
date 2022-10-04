# (ↄ) 2017-2022 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3
import base64, datetime, json, re, requests, uuid
from typing import Optional, Union
from bs4 import BeautifulSoup

SPLATNET3_URL = "https://api.lp1.av5ja.srv.nintendo.net"
GRAPHQL_URL  = "https://api.lp1.av5ja.srv.nintendo.net/api/graphql"
WEB_VIEW_VERSION = "1.0.0-216d0219" # fallback
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
	'CoopHistoryDetailQuery':          'f3799a033f0a7ad4b1b396f9a3bafb1e', # SR  / req "coopHistoryDetailId" - query2
}

def get_web_view_ver() -> str:
	'''Find & parse the SplatNet 3 main.js file for the current site version.

	Returns:
		str: The current site version.
	'''

	splatnet3_home = requests.get(SPLATNET3_URL)
	soup = BeautifulSoup(splatnet3_home.text, "html.parser")

	main_js = soup.select_one("script[src*='static']")
	if not main_js:
		return WEB_VIEW_VERSION

	main_js_url = SPLATNET3_URL + main_js.attrs["src"]
	main_js_body = requests.get(main_js_url)

	pattern = r"\b(?P<revision>[0-9a-f]{40})\b.*revision_info_not_set\"\),.*?=\"(?P<version>\d+\.\d+\.\d+)"
	match = re.search(pattern, main_js_body.text)
	if match is None:
		return WEB_VIEW_VERSION

	version, revision = match.group("version"), match.group("revision")
	return f"{version}-{revision[:8]}"


def set_noun(which: str) -> str:
	'''Returns the term to be used when referring to the type of results in question.

	Args:
		which (str): The type of results in question. Can be "ink", "salmon", or "both".
	
	Returns:
		str: The corresponding term to print.
	'''

	if which == "both":
		return "battles/jobs"
	elif which == "salmon":
		return "jobs"
	else: # "ink"
		return "battles"


def b64d(string: str) -> Union[str, int]:
	'''Base64 decode a string and cut off the SplatNet prefix.'''

	thing_id = base64.b64decode(string).decode('utf-8')
	thing_id = thing_id.replace("VsStage-", "")
	thing_id = thing_id.replace("VsMode-", "")
	thing_id = thing_id.replace("Weapon-", "")
	thing_id = thing_id.replace("CoopStage-", "")
	thing_id = thing_id.replace("CoopGrade-", "")
	if thing_id[:15] == "VsHistoryDetail" or thing_id[:17] == "CoopHistoryDetail":
		return thing_id # string
	else:
		return int(thing_id) # integer


def epoch_time(time_string: str) -> int:
	'''Converts a playedTime string into an int representing the epoch time.

	Args:
		time_string (str): The string to convert. Should be in the format `%Y-%m-%dT%H:%M:%SZ`.
	
	Returns:
		int: The corresponding epoch time.
	'''

	utc_time = datetime.datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")
	epoch_time = int((utc_time - datetime.datetime(1970, 1, 1)).total_seconds())
	return epoch_time


def gen_graphql_body(sha256hash: str, varname: Optional[str] = None, varvalue: Optional[str] = None) -> str:
	'''Generates and serializes a JSON dictionary, specifying information to retrieve, to send with GraphQL requests.
	
	Args:
		sha256hash (str): The SHA256 hash of the query to send. A list of hashes can be found in `translate_rid`.
		varname (Optional[str], optional): The name of the variable to send. Defaults to None.
		varvalue (Optional[str], optional): The value of the variable to send. Defaults to None.
	
	Returns:
		str: The serialized JSON dictionary.
	'''
	great_passage = {
		"extensions": {
			"persistedQuery": {
				"sha256Hash": sha256hash,
				"version": 1
			}
		},
		"variables": {}
	}

	if varname != None and varvalue != None:
		great_passage["variables"][varname] = varvalue

	return json.dumps(great_passage)


def custom_key_exists(key, config_data, value=True):
	'''Checks if a given custom key exists in config.txt and is set to the specified value (true by default).'''

	# https://github.com/frozenpandaman/s3s/wiki/config-keys
	if key not in SUPPORTED_KEYS:
		print("(!) Checking unexpected custom key")
	return config_data.get(key, None) == str(value).lower()
