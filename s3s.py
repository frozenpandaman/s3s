#!/usr/bin/env python
# s3s (ↄ) 2022 eli fessler (frozenpandaman), clovervidia
# Based on splatnet2statink (ↄ) 2017-2022 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3

import sys, os, requests, json, time, datetime, argparse, msgpack, re
from PIL import Image, ImageDraw
from packaging import version
import iksm
from bs4 import BeautifulSoup

A_VERSION = "0.0.4"

print(f"s3s v{A_VERSION}")

# CONFIG.TXT CREATION
if getattr(sys, 'frozen', False): # place config.txt in same directory as script (bundled or not)
	app_path = os.path.dirname(sys.executable)
elif __file__:
	app_path = os.path.dirname(__file__)
config_path = os.path.join(app_path, "config.txt")

try:
	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)
	config_file.close()
except (IOError, ValueError):
	print("Generating new config file.")
	CONFIG_DATA = {"api_key": "", "acc_loc": "", "gtoken": "", "bullettoken": "", "session_token": "", "f_gen": "https://api.imink.app/f"}
	config_file = open(config_path, "w")
	config_file.seek(0)
	config_file.write(json.dumps(CONFIG_DATA, indent=4, sort_keys=True, separators=(',', ': ')))
	config_file.close()
	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)
	config_file.close()

# SET GLOBALS
API_KEY       = CONFIG_DATA["api_key"]       # for stat.ink
USER_LANG     = CONFIG_DATA["acc_loc"][:5]   # nintendo account info
USER_COUNTRY  = CONFIG_DATA["acc_loc"][-2:]  # nintendo account info
GTOKEN        = CONFIG_DATA["gtoken"]        # for accessing splatnet - base64
BULLETTOKEN   = CONFIG_DATA["bullettoken"]   # for accessing splatnet - base64 JWT
SESSION_TOKEN = CONFIG_DATA["session_token"] # for nintendo login
F_GEN_URL     = CONFIG_DATA["f_gen"]         # endpoint for generating f (imink API by default)
# UNIQUE_ID     = CONFIG_DATA["app_unique_id"] # NPLN player ID

SPLATNET3_URL = "https://api.lp1.av5ja.srv.nintendo.net"
GRAPHQL_URL  = "https://api.lp1.av5ja.srv.nintendo.net/api/graphql"

WEB_VIEW_VERSION = "1.0.0-d3a90678"

# SET HTTP HEADERS
if "app_user_agent" in CONFIG_DATA:
	APP_USER_AGENT = str(CONFIG_DATA["app_user_agent"])
else:
	APP_USER_AGENT = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) ' \
		'AppleWebKit/537.36 (KHTML, like Gecko) ' \
		'Chrome/94.0.4606.61 Mobile Safari/537.36'

# SHA256 hash database for SplatNet 3 GraphQL queries
# full list: https://github.com/samuelthomas2774/nxapi/discussions/11#discussioncomment-3614603
translate_rid = {
	'HomeQuery':                       'dba47124d5ec3090c97ba17db5d2f4b3', # blank vars
	'LatestBattleHistoriesQuery':      '7d8b560e31617e981cf7c8aa1ca13a00', # INK / blank vars - query1
	'RegularBattleHistoriesQuery':     '819b680b0c7962b6f7dc2a777cd8c5e4', # INK / blank vars - query1
	'BankaraBattleHistoriesQuery':     'c1553ac75de0a3ea497cdbafaa93e95b', # INK / blank vars - query1
	'PrivateBattleHistoriesQuery':     '51981299595060692440e0ca66c475a1', # INK / blank vars - query1
	'VsHistoryDetailQuery':            'cd82f2ade8aca7687947c5f3210805a6', # INK / req "vsResultId" - query2
	'CoopHistoryQuery':                '817618ce39bcf5570f52a97d73301b30', # SR  / blank vars - query1
	'CoopHistoryDetailQuery':          'f3799a033f0a7ad4b1b396f9a3bafb1e', # SR  / req "coopHistoryDetailId" - query2
}

def get_web_view_ver():
	'''Find & parse the SplatNet 3 main.js file for the current site version.'''

	splatnet3_home = requests.get(SPLATNET3_URL)
	soup = BeautifulSoup(splatnet3_home.text, "html.parser")

	main_js = soup.select_one("script[src*='static']")
	if not main_js:
		return WEB_VIEW_VERSION

	main_js_url = SPLATNET3_URL + main_js.attrs["src"]
	main_js_body = requests.get(main_js_url)

	match = re.search(r"\b(\d+\.\d+\.\d+)\b-\".concat.*?\b([0-9a-f]{40})\b", main_js_body.text)
	if not match:
		return WEB_VIEW_VERSION

	version, revision = match.groups()
	return f"{version}-{revision[:8]}"

def headbutt():
	'''Return a (dynamic!) header used for GraphQL requests.'''

	graphql_head = {
		'Authorization':    f'Bearer {BULLETTOKEN}', # update every time it's called with current global var
		'Accept-Language':  USER_LANG,
		'User-Agent':       APP_USER_AGENT,
		'X-Web-View-Ver':   get_web_view_ver(),
		'Content-Type':     'application/json',
		'Accept':           '*/*',
		'Origin':           'https://api.lp1.av5ja.srv.nintendo.net',
		'X-Requested-With': 'com.nintendo.znca',
		'Referer':          f'https://api.lp1.av5ja.srv.nintendo.net/?lang={USER_LANG}&na_country={USER_COUNTRY}&na_lang={USER_LANG}',
		'Accept-Encoding': 'gzip, deflate'
	}
	return graphql_head

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
	thing_id = thing_id.replace("Weapon-", "")
	thing_id = thing_id.replace("CoopStage-", "")
	thing_id = thing_id.replace("CoopGrade-", "")
	if thing_id[:15] == "VsHistoryDetail" or thing_id[:17] == "CoopHistoryDetail":
		return thing_id[-36:] # uuid
	else:
		return int(thing_id) # integer


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

	if varname != None and varvalue != None:
		great_passage["variables"][varname] = varvalue

	return json.dumps(great_passage)


def write_config(tokens):
	'''Writes config file and updates the global variables.'''

	config_file = open(config_path, "w")
	config_file.seek(0)
	config_file.write(json.dumps(tokens, indent=4, sort_keys=True, separators=(',', ': ')))
	config_file.close()

	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)

	global API_KEY
	API_KEY = CONFIG_DATA["api_key"]
	global USER_LANG
	USER_LANG = CONFIG_DATA["acc_loc"][:5]
	global USER_COUNTRY
	USER_COUNTRY = CONFIG_DATA["acc_loc"][-2:]
	global GTOKEN
	GTOKEN = CONFIG_DATA["gtoken"]
	global BULLETTOKEN
	BULLETTOKEN = CONFIG_DATA["bullettoken"]
	global SESSION_TOKEN
	SESSION_TOKEN = CONFIG_DATA["session_token"]

	config_file.close()


def custom_key_exists(key, value=True):
	'''Checks if a given custom key exists in config.txt and is set to the specified value (true by default).'''

	# https://github.com/frozenpandaman/s3s/wiki/config-keys
	if key not in ["ignore_private", "app_user_agent"]:
		print("(!) checking unexpected custom key")
	return True if key in config_data and config_data[key].lower() == str(value).lower() else False


def prefetch_checks():
	'''Queries the SplatNet 3 homepage to check if our gtoken cookie and bulletToken are still valid, otherwise regenerate.'''

	if SESSION_TOKEN == "" or GTOKEN == "" or BULLETTOKEN == "":
		gen_new_tokens("blank")

	sha = translate_rid["HomeQuery"]
	test = requests.post(GRAPHQL_URL, data=gen_graphql_body(sha), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
	if test.status_code != 200:
		gen_new_tokens("expiry")


def gen_new_tokens(reason, force=False):
	'''Attempts to generate new tokens when the saved ones have expired.'''

	manual_entry = False
	if force != True: # unless we force our way through
		if reason == "blank":
			print("Blank token(s).")
		elif reason == "expiry":
			print("The stored tokens have expired.")
		else:
			print("Cannot access SplatNet 3 without having played online.")
			sys.exit(1)

	if SESSION_TOKEN == "":
		print("Please log in to your Nintendo Account to obtain your session_token.")
		new_token = iksm.log_in(A_VERSION)
		if new_token == None:
			print("There was a problem logging you in. Please try again later.")
		elif new_token == "skip":
			manual_entry = True
		else:
			print("\nWrote session_token to config.txt.")
		CONFIG_DATA["session_token"] = new_token
		write_config(CONFIG_DATA)
	elif SESSION_TOKEN == "skip":
		manual_entry = True

	if manual_entry: # no session_token ever gets stored
		print("\nYou have opted against automatic token generation and must manually input your tokens.\n")
		new_gtoken, new_bullettoken = iksm.enter_tokens()
		acc_lang = "en-US"
		acc_country = "US"
		print("Using `en-US` for language and `US` for country by default. These can be changed in config.txt.")
	else:
		print("Attempting to generate new gtoken and bulletToken...")
		new_gtoken, acc_name, acc_lang, acc_country = iksm.get_gtoken(F_GEN_URL, SESSION_TOKEN, A_VERSION)
		new_bullettoken = iksm.get_bullet(new_gtoken, get_web_view_ver(), APP_USER_AGENT, acc_lang, acc_country)
	CONFIG_DATA["gtoken"] = new_gtoken # valid for 2 hours
	CONFIG_DATA["bullettoken"] = new_bullettoken # valid for 2 hours
	CONFIG_DATA["acc_loc"] = acc_lang + "|" + acc_country
	write_config(CONFIG_DATA)

	if manual_entry:
		print("Wrote tokens to config.txt.")
	else:
		print(f"Wrote tokens for {acc_name} to config.txt.")


def fetch_json(which, separate=False, exportall=False, specific=False):
	'''Returns results JSON from SplatNet 3, including a combined dict for ink battles + SR jobs if requested.'''

	if exportall and not separate:
		print("fetch_json() must be called with separate=True if using exportall.")
		sys.exit(1)

	prefetch_checks()

	ink_list, salmon_list = [], []
	parent_files = []

	sha_list = []
	if which == "both" or which == "ink":
		if specific == True or specific == "regular":
			sha_list.append(translate_rid["RegularBattleHistoriesQuery"])
		if specific == True or specific == "anarchy":
			sha_list.append(translate_rid["BankaraBattleHistoriesQuery"])
		if specific == True or specific == "private":
			sha_list.append(translate_rid["PrivateBattleHistoriesQuery"])
		else:
			sha_list.append(translate_rid["LatestBattleHistoriesQuery"])
	else:
		sha_list.append(None)
	if which == "both" or which == "salmon":
		sha_list.append(translate_rid["CoopHistoryQuery"])
	else:
		sha_list.append(None)

	for sha in sha_list:
		if sha != None:
			battle_ids, job_ids = [], []

			query1 = requests.post(GRAPHQL_URL, data=gen_graphql_body(sha), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
			query1_resp = json.loads(query1.text)

			# ink battles - latest 50 of any type
			if "latestBattleHistories" in query1_resp["data"]:
				for battle_group in query1_resp["data"]["latestBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"])
			# ink battles - latest 50 turf war
			elif "regularBattleHistories" in query1_resp["data"]:
				for battle_group in query1_resp["data"]["regularBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"])
			# ink battles - latest 50 ranked battles
			elif "bankaraBattleHistories" in query1_resp["data"]:
				for battle_group in query1_resp["data"]["bankaraBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"])
			# ink battles - latest 50 private battles
			elif "privateBattleHistories" in query1_resp["data"]:
				for battle_group in query1_resp["data"]["privateBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"])
			# salmon run jobs - latest 50
			elif "coopResult" in query1_resp["data"]:
				for shift in query1_resp["data"]["coopResult"]["historyGroups"]["nodes"]:
					for job in shift["historyDetails"]["nodes"]:
						job_ids.append(job["id"])

			job_ids = list(dict.fromkeys(job_ids)) # remove duplicates. salmon run job list has no dupes

			for bid in battle_ids:
				query2_b = requests.post(GRAPHQL_URL,
					data=gen_graphql_body(translate_rid["VsHistoryDetailQuery"], "vsResultId", bid),
					headers=headbutt(),
					cookies=dict(_gtoken=GTOKEN))
				query2_resp_b = json.loads(query2_b.text)
				ink_list.append(query2_resp_b)

			for jid in job_ids:
				query2_j = requests.post(GRAPHQL_URL,
					data=gen_graphql_body(translate_rid["CoopHistoryDetailQuery"], "coopHistoryDetailId", jid),
					headers=headbutt(),
					cookies=dict(_gtoken=GTOKEN))
				query2_resp_j = json.loads(query2_j.text)
				salmon_list.append(query2_resp_j)

			parent_files.append(query1_resp)
		else: # sha = None (we don't want to get the specified result type)
			pass

	if exportall:
		return parent_files, ink_list, salmon_list
	elif separate:
		return ink_list, salmon_list
	else:
		return ink_list + salmon_list


def update_salmon_profile():
	''' Updates stat.ink Salmon Run stats/profile.'''

	pass # TODO

	# prefetch_checks()

	# old code
	# .../api/coop_results - need stat.ink s3 support
	# results_list = requests.get(url, headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
	# data = json.loads(results_list.text)
	# profile = data["summary"]

	# payload = {
	# 	"work_count":        profile["card"]["job_num"],
	# 	"total_golden_eggs": profile["card"]["golden_ikura_total"],
	# 	"total_eggs":        profile["card"]["ikura_total"],
	# 	"total_rescued":     profile["card"]["help_total"],
	# 	"total_point":       profile["card"]["kuma_point_total"]
	# 	# TODO - other new things - fish scales, xtrawave stuff?, etc.
	# }

	# url  = "https://stat.ink/api/v2/salmon-stats" # TODO - need stat.ink s3 support
	# auth = {'Authorization': f'Bearer {API_KEY}'}
	# updateprofile = requests.post(url, headers=auth, data=payload)

	# if updateprofile.ok:
	# 	print("Successfully updated your Salmon Run profile.")
	# else:
	# 	print("Could not update your Salmon Run profile. Error from stat.ink:")
	# 	print(updateprofile.text)


def prepare_battle_result(battle):
	'''Converts the Nintendo JSON format for a Turf War/Ranked battle to the stat.ink one.'''

	payload = {}
	battle = battle["data"]["vsHistoryDetail"]

	## UUID ##
	##########
	# payload["uuid"] = b64d(battle["id"])

	## SPLASHTAG ##
	###############
	# title = battle["player"]["byname"]
	# username = battle["player"]["name"]
	# name_id = battle["player"]["nameId"]
	# username_color (dict of r, g, b, a) = battle["player"]["nameplate"]["background"]["textColor"]
	# badge_urls = parse to data - battle["player"]["nameplate"]["badges"][i]["image"]["url"]
	# background = parse to data - battle["player"]["nameplate"]["background"]["image"]["url"]

	## MODE ##
	##########
	mode = battle["vsMode"]["mode"]
	if mode == "REGULAR":
		payload["lobby"] = "regular"
	elif mode == "BANKARA":
		if battle["bankaraMatch"]["mode"] == "OPEN":
			payload["lobby"] = "bankara_open"
		elif battle["bankaraMatch"]["mode"] == "CHALLENGE":
			payload["lobby"] = "bankara_challenge"
	elif mode == "PRIVATE":
		payload["lobby"] = "private"
	# TODO - splatfest stuff

	## RULE ##
	##########
	rule = battle["vsRule"]["rule"]
	if rule == "TURF_WAR":
		payload["rule"] = "nawabari"
	elif rule == "AREA":
		payload["rule"] = "area"
	elif rule == "LOFT":
		payload["rule"] = "yagura"
	elif rule == "GOAL":
		payload["rule"] = "hoko"
	elif rule == "CLAM":
		payload["rule"] = "asari"

	## STAGE ##
	###########
	# hardcoded in alpha
	stage_id = b64d(battle["vsStage"]["id"])
	if stage_id == 1:
		payload["stage"] = "gorge" # yunohana
	elif stage_id == 2:
		payload["stage"] = "alley" # gonzui
	elif stage_id == 3:
		payload["stage"] = "market" # yagara
	elif stage_id == 4:
		payload["stage"] = "spillway" # mategai
	elif stage_id == 6:
		payload["stage"] = "metalworks" # namero
	elif stage_id == 10:
		payload["stage"] = "bridge" # masaba
	elif stage_id == 11:
		payload["stage"] = "museum" # kinmedai
	elif stage_id == 12:
		payload["stage"] = "resort" # mahimahi
	elif stage_id == 13:
		payload["stage"] = "academy" # amabi
	elif stage_id == 14:
		payload["stage"] = "shipyard" # chozame
	elif stage_id == 15:
		payload["stage"] = "mart" # zatou
	elif stage_id == 16:
		payload["stage"] = "world" # sumeshi

	## WEAPON, K/D, TURF INKED ##
	############
	for teammate in battle["myTeam"]["players"]:
		if player["isMyself"] == True:
			payload["weapon"]         = b64d(player["weapon"]["id"])
			payload["kill"]           = player["result"]["kill"]
			payload["assist"]         = player["result"]["assist"]
			payload["kill_or_assist"] = payload["kill"] + payload["assist"]
			payload["death"]          = player["result"]["death"]
			payload["special"]        = player["result"]["special"]
			# payload["inked"]          = player["paint"] # TODO - check how bonus works?? two diff values?
			# player["result"]["noroshiTry"] = ultra signal attempts
			payload["species"]        = player["species"].lower() # not supported for now


	## RESULT ##
	############
	result = battle["myTeam"]["judgement"]
	if result == "WIN":
		payload["result"] = "win"
	elif result == "LOSE":
		payload["result"] = "lose"
	elif result == "DRAW":
		payload["result"] = "draw"

	## LEVEL ## TODO
	###########
	# payload["level_before"] = ...
	# payload["level_after"]  = ...

	## CASH ## TODO
	##########
	# payload["cash_before"] = ...
	# payload["cash_after"] = ...

	## START/END TIMES ##
	#####################
	time_string         = battle["playedTime"] # UTC
	utc_time            = datetime.datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%SZ")
	epoch_time          = int((utc_time - datetime.datetime(1970, 1, 1)).total_seconds())
	payload["start_at"] = epoch_time
	payload["end_at"]   = epoch_time + battle["duration"]

	## RANK IN TEAM ## TODO
	##################
	# payload["rank_in_team"] = 1, 2, 3, 4

	# Turf War only (NOT TRICOLOR)
	if mode == "REGULAR":
		payload["our_team_percent"]   = float(battle["myTeam"]["result"]["paintRatio"]) * 100
		payload["their_team_percent"] = float(battle["otherTeams"][0]["result"]["paintRatio"]) * 100

		our_team_inked, their_team_inked = 0, 0
		for player in battle["myTeam"]["players"]:
			our_team_inked += player["paint"]
		for player in battle["otherTeams"][0]["players"]:
			their_team_inked += player["paint"]
		payload["our_team_inked"] = our_team_inked
		payload["their_team_inked"] = their_team_inked

	# Anarchy Battles only
	if mode == "BANKARA":
		payload["our_team_count"]   = battle["myTeam"]["result"]["score"]
		payload["their_team_count"] = battle["otherTeams"][0]["result"]["score"]
		payload["knockout"] = "yes" if battle["knockout"] != "NEITHER" else "no" # or check if either == 100

	# TODO old code - have to get from parent request
	# 	try:  # not present in all modes
	# 		rank_after             = battle["udemae"]["name"].lower()
	# 		rank_before            = battle["player_result"]["player"]["udemae"]["name"].lower()
	# 		rank_s_plus_num_after  = battle["udemae"]["s_plus_number"]
	# 		rank_s_plus_num_before = battle["player_result"]["player"]["udemae"]["s_plus_number"]
	# 	except:
	# 		rank_after, rank_before, rank_s_plus_num_after, rank_s_plus_num_before = None, None, None, None

	# 	payload["rank_after"]         = rank_after
	# 	payload["rank_before"]        = rank_before
	# 	payload["rank_after_s_plus"]  = rank_s_plus_num_after
	# 	payload["rank_before_s_plus"] = rank_s_plus_num_before

	# 	payload["rank_before_exp"] = ...
	# 	payload["rank_after_exp"] = ...

		# payload["image_judge"] = ... # judd screen
		# payload["image_result"] = ... # full scoreboard
		# payload["image_gear"] = ... # gear

	payload["automated"] = "yes" # data was not manually entered!
	payload["splatnet_json"] = json.dumps(battle)

	return payload


def prepare_job_result(battle):
	'''Converts the Nintendo JSON format for a Salmon Run job to the stat.ink one.'''

	pass # TODO
	# combo of set_teammates() + salmon_post_shift()
	# set payload["splatnet_json"]


def post_result(data, isblackout, istestrun):
	'''Uploads battle/job JSON to stat.ink, and prints the returned URL or error message..'''

	try:
		results = data["results"] # list of dictionaries - TODO might be diff
	except KeyError:
		results = [data] # single battle/job

	# filter down to one battle at a time
	for i in range(len(results)):
		if "vsHistoryDetail" in results[i]["data"]: # ink battle
			payload = prepare_battle_result(results[i]["data"])
		elif "coopHistoryDetail" in results[i]["data"]: # salmon run job
			payload = prepare_job_result(results[i]["data"])
		else: # shouldn't happen
			print("Ill-formatted JSON while uploading. Exiting.")
			sys.exit(1)

		if payload["lobby"] == "private" and custom_key_exists("ignore_private"): # TODO - also check salmon run?
			continue

		# TODO - do stuff with isblackout - check for salmon run too??

		s3s_values = {'agent': '\u0073\u0033\u0073', 'agent_version': A_VERSION} # lol
		s3s_values["agent_variables"] = {} # TODO - monitoring mode or not
		payload.update(s3s_values)

		if payload["agent"][0:3] != os.path.basename(__file__)[:-3]:
			print("Could not upload. Please contact @frozenpandaman on GitHub for assistance.")
			sys.exit(1)

		if istestrun:
			payload["test"] = "yes"

		# post
		url  = "https://stat.ink/api/v3/battle"
		auth = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/x-msgpack'}
		postbattle = requests.post(url, headers=auth, data=msgpack.packb(payload), allow_redirects=False)

		# response
		headerloc = postbattle.headers.get('location')
		if headerloc != None:
			if postbattle.status_code == 302: # redirect
				print(f"Battle already uploaded - {headerloc}")
			else: # 200 OK
				print(f"Battle uploaded to {headerloc}")
		else: # error
			print("Error uploading battle. Message from server:")
			print(postbattle.content.decode('utf-8'))


def check_for_updates():
	'''Checks the script version against the repo, reminding users to update if available.'''

	print("While s3s is in alpha, please update the script regularly via `git pull`.")
	# try:
	# 	latest_script = requests.get("https://raw.githubusercontent.com/frozenpandaman/s3s/master/s3s.py")
	# 	new_version = re.search(r'A_VERSION = "([\d.]*)"', latest_script.text).group(1)
	# 	update_available = version.parse(new_version) > version.parse(A_VERSION)
	# 	if update_available:
	# 		print(f"\nThere is a new version (v{new_version}) available.", end='')
	# 		if os.path.isdir(".git"):
	# 			update_now = input("\nWould you like to update now? [Y/n] ")
	# 			if update_now == "" or update_now[0].lower() == "y":
	# 				FNULL = open(os.devnull, "w")
	# 				call(["git", "checkout", "."], stdout=FNULL, stderr=FNULL)
	# 				call(["git", "checkout", "master"], stdout=FNULL, stderr=FNULL)
	# 				call(["git", "pull"], stdout=FNULL, stderr=FNULL)
	# 				print(f"Successfully updated to v{new_version}. Please restart s3s.")
	# 				return True
	# 			else:
	# 				print("Remember to update later with `git pull` to get the latest version.\n")
	# 		else: # no git directory
	# 			print(" Visit the site below to update:\nhttps://github.com/frozenpandaman/s3s\n")
	# except: # if there's a problem connecting to github
	# 	pass


def check_statink_key():
	'''Checks if a valid length API key has been provided and, if not, prompts the user to enter one.'''

	if API_KEY == "skip":
		return
	elif len(API_KEY) != 43:
		new_api_key = ""
		while len(new_api_key.strip()) != 43 and new_api_key.strip() != "skip":
			if new_api_key.strip() == "" and API_KEY.strip() == "":
				new_api_key = input("stat.ink API key: ")
			else:
				print("Invalid stat.ink API key. Please re-enter it below.")
				new_api_key = input("stat.ink API key: ")
			CONFIG_DATA["api_key"] = new_api_key
		write_config(CONFIG_DATA)
	return


def get_num_results(which):
	'''I/O for getting number of battles/jobs to upload.'''

	noun = set_noun(which)
	try: # TODO - can be above 50 if combined tw/anarchy/private results. do stuff with 'specific=...'
		n = int(input(f"Number of recent {noun} to upload (0-50)? "))
	except ValueError:
		print("Please enter an integer between 0 and 50. Exiting.")
		sys.exit(1)
	if n < 1:
		print("Exiting without uploading anything.")
		sys.exit(0)
	elif n > 50:
		print(f"SplatNet 3 only stores the 50 most recent {noun}. Exiting.")
		sys.exit(1)
	else:
		return n


def check_if_missing(which, isblackout, istestrun):
	'''Checks for unuploaded battles, and uploads any that are found.'''

	noun = set_noun(which)
	print(f"Checking if there are previously-unuploaded {noun}...")

	urls = []
	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Get-UUID-List-(for-s3s)
	if which == "both" or which == "ink":
		urls.append("https://stat.ink/api/v3/s3s/uuid-list") # max 200 entries
	else:
		urls.append(None)
	# if which == "both" or which == "salmon":
		# urls.append("...")
	# else:
		# urls.append(None)

	noun = "battles" # first (and maybe only)
	for url in urls:
		if url != None:
			printed = False
			auth = {'Authorization': f'Bearer {API_KEY}'}
			resp = requests.get(url, headers=auth) # no params = all: regular, bankara, private
			try:
				statink_uploads = json.loads(resp.text)
			except:
				print(f"Encountered an error while checking recently-uploaded {noun}. Is stat.ink down?")
				sys.exit(1)

			# ! fetch from online
			results = fetch_json(which) # don't need to set 'specific' - should all be within 'latest'

			splatnet_results = [] # 50 recent battles/jobs on splatnet
			for i, result in reversed(list(enumerate(results))):
				try: # ink battle
					num = b64d(result["VsHistoryDetail"]["id"])
				except KeyError: # salmon run job
					try:
						num = b64d(result["CoopHistoryDetail"]["id"])
					except:
						print(f"Ill-formatted JSON while checking missing {noun}. Exiting.")
						sys.exit(1)
				splatnet_results.append(num)
				if num not in statink_uploads: # one of the splatnet entries isn't on stat.ink (unuploaded)
					if not printed:
						printed = True
						print(f"Previously-unuploaded {noun} detected. Uploading now...")
					post_result(results[i], isblackout, istestrun)

			if not printed:
				print(f"No previously-unuploaded {noun} found.")

		noun = "jobs" # for second run through the loop


def monitor_battles(which, secs, isblackout, istestrun):
	'''Monitors JSON for changes/new battles and uploads them.'''

	# ! fetch from online
	battles_results, jobs_results = fetch_json(which, separate=True) # don't need to set 'specific' - should all be within 'latest'

	cached_battles = []
	cached_jobs = []
	for result in reversed(battles_results):
		cached_battles.append(int(result["battle_number"]))
	for result in reversed(jobs_results):
		cached_jobs.append(int(result["job_id"]))

	# counters
	battle_wins, battle_losses, splatfest_wins, splatfest_losses, mirror_matches = [0]*5 # init all to 0
	job_successes, job_failures = [0]*2

	mins = str(round(float(secs)/60.0, 2))
	mins = mins[:-2] if mins[-2:] == ".0" else mins
	print(f"Waiting for new {set_noun(which)}... (checking every {mins} minutes)")

	try:
		while True:
			for i in range(secs, -1, -1):
				sys.stdout.write(f"Press Ctrl+C to exit. {i} ")
				sys.stdout.flush()
				time.sleep(1)
				sys.stdout.write("\r")

			# ! fetch from online
			ink_results, salmon_results = fetch_json(which, separate=True) # don't need to set 'specific' - should all be within 'latest'

			if which == "both" or which == "ink":
				for i, result in reversed(list(enumerate(battles_results))):
					if int(result["battle_number"]) not in cached_battles:
						if result["game_mode"]["key"] == "private" and custom_key_exists("ignore_private"):
							pass
						else:
							outcome = "Won" if result["my_team_result"]["key"] == "victory" else "Lost"
							splatfest_match = True if result["game_mode"]["key"] in ["fes_solo", "fes_team"] else False
							if splatfest_match: # keys will exist
								our_key = result["my_team_fes_theme"]["key"]
								their_key = result["other_team_fes_theme"]["key"]
								mirror_match = True if our_key == their_key else False
							if outcome == "Won":
								battle_wins += 1
								if splatfest_match and not mirror_match:
									splatfest_wins += 1
							else: # Lost
								battle_losses += 1
								if splatfest_match and not mirror_match:
									splatfest_losses += 1
							if splatfest_match and mirror_match:
								mirror_matches += 1
							# stagename = "..." # TODO - get short name??
							dt = datetime.datetime.fromtimestamp(int(result["start_time"])).strftime('%I:%M:%S %p').lstrip("0")
							# print(f"New battle result detected at {dt}! ({stagename}, {outcome})")
							print(f"New battle result detected at {dt}! ({outcome})") # TODO - temp workaround
						cached_battles.append(int(result["battle_number"]))
						post_result(result, isblackout, istestrun)

			if which == "both" or which == "salmon":
				for i, result in reversed(list(enumerate(jobs_results))):
					if int(result["job_id"]) not in cached_jobs:
						if result["game_mode"]["key"] == "private" and custom_key_exists("ignore_private"):
							pass
						else:
							outcome = "Success" if result["job_result"]["is_clear"] == True else "Failure"
							if outcome == "Success":
								job_successes += 1
							else: # Failure
								job_failures += 1
							# stagename = "..." # TODO - get short name??
							dt = datetime.datetime.fromtimestamp(int(result["start_time"])).strftime('%I:%M:%S %p').lstrip("0")
							# print(f"New job result detected at {dt}! ({stagename}, {outcome})")
							print(f"New job result detected at {dt}! ({outcome})") # TODO - temp workaround
							cached_jobs.append(int(result["job_id"]))
							post_result(result, isblackout, istestrun)

	except KeyboardInterrupt:
		# print(f"\nChecking to see if there are unuploaded {set_noun(which)} before exiting...")
		# TODO
		# do update_salmon_profile() at end if salmon run
		print("Checking for unuploaded results before exiting is not yet implemented.")
		print("Bye!")


def main():
	'''Main process, including I/O and setup.'''

	# setup
	#######
	check_for_updates()
	# check_statink_key() # TODO - temp. disabled

	# argparse stuff
	################
	parser = argparse.ArgumentParser()
	parser.add_argument("-M", dest="N", required=False, nargs="?", action="store",
		help="monitoring mode; pull data every N secs (default: 300)", const=300)
	parser.add_argument("-r", required=False, action="store_true",
		help="retroactively post unuploaded battles/jobs")
	parser.add_argument("-nsr", required=False, action="store_true",
						help="do not check for Salmon Run jobs")
	parser.add_argument("-osr", required=False, action="store_true",
						help="only check for Salmon Run jobs")
	parser.add_argument("--blackout", required=False, action="store_true",
		help="black out names on scoreboard result images")

	parser.add_argument("-t", required=False, action="store_true",
		help="dry run for testing (won't post to stat.ink)")
	parser.add_argument("-i", dest="filename", required=False, help=argparse.SUPPRESS)
	parser.add_argument("-o", required=False, action="store_true", help=argparse.SUPPRESS)

	parser_result = parser.parse_args()

	# regular args
	n_value     = parser_result.N
	check_old   = parser_result.r
	only_ink    = parser_result.nsr # ink battles ONLY
	only_salmon = parser_result.osr # salmon run ONLY
	blackout    = parser_result.blackout

	# testing/dev stuff
	test_run = parser_result.t
	filename = parser_result.filename # intended for results json or battle files
	outfile  = parser_result.o # output to local files

	# i/o checks
	############
	if only_ink and only_salmon:
		print("That doesn't make any sense! :) Exiting.")
		sys.exit(1)

	if filename and len(sys.argv) > 2:
		print("Cannot use -i with other arguments. Exiting.")
		sys.exit(1)
	elif outfile and len(sys.argv) > 2:
		print("Cannot use -o with other arguments. Exiting.")
		sys.exit(1)

	secs = -1
	if n_value != None:
		try:
			secs = int(parser_result.N)
		except ValueError:
			print("Number provided must be an integer. Exiting.")
			sys.exit(1)
		if secs < 0:
				print("No.")
				sys.exit(1)
		elif secs < 60:
				print("Minimum number of seconds in monitoring mode is 60. Exiting.")
				sys.exit(1)

	# exporting results to file
	###########################
	if outfile:
		prefetch_checks()
		print("\nFetching your JSON files to export locally... this might take a while.")
		try:
			# fetch_json() calls prefetch_checks() to gen or check tokens
			parents, results, coop_results = fetch_json("both", separate=True, exportall=True, specific=True)
		except Exception as e:
			print("Ran into an error:")
			print(e)
			print("Please run the script again.")
			sys.exit(1)

		cwd = os.getcwd()
		export_dir = os.path.join(cwd, f'export-{int(time.time())}')
		if not os.path.exists(export_dir):
			os.makedirs(export_dir)

		if parents != None:
			with open(os.path.join(cwd, export_dir, "overview.json"), "x") as fout:
				json.dump(parents, fout)
				print("Created overview.json with general info about your battle and job stats.")

		if results != None:
			with open(os.path.join(cwd, export_dir, "results.json"), "x") as fout:
				json.dump(results, fout)
				print("Created results.json with detailed recent battle stats (up to 50 of each type).")

		if coop_results != None:
			with open(os.path.join(cwd, export_dir, "coop_results.json"), "x") as fout:
				json.dump(coop_results, fout)
				print("Created coop_results.json with detailed recent Salmon Run job stats (up to 50).")

		print("\nHave fun playing Splatoon 3! :) Bye!")
		sys.exit(0)

	# manual json upload
	####################
	if filename:
		if not os.path.exists(filename):
			argparse.ArgumentParser().error(f"File {filename} does not exist!") # exit
		with open(filename) as data_file:
			try:
				data = json.load(data_file)
			except ValueError:
				print("Could not decode JSON object in this file.")
				sys.exit(1)
		post_result(data, blackout, test_run) # one or multiple
		sys.exit(0)

	# regular run
	#############
	which = "ink" if only_ink else "salmon" if only_salmon else "both"

	# ---
	# TEMP. UNTIL STAT.INK SUPPORTS S3
	print("\nNOTE: stat.ink does not yet support Splatoon 3. Re-run the script with the -o flag " \
		"to save your current SplatNet 3 results (up to most recent 50 battles & jobs) to JSON files, " \
		"which can later be manually uploaded with -i file.json. This message will be removed when support is added.")
	sys.exit(0)
	# ---

	if which != "ink":
		update_salmon_profile()

	if check_old:
		check_if_missing(which, blackout, test_run)
	if secs != -1: # monitoring mode
		monitor_battles(which, secs, blackout, test_run)
	else: # regular mode (no -M)
		n = get_num_results(which)
		print("Pulling data from online...")

		# ! fetch from online
		results = fetch_json(which)

		for i in reversed(range(n)):
			post_result(results[i], blackout, test_run)


if __name__ == "__main__":
	main()
