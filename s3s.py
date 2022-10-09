#!/usr/bin/env python
# s3s (ↄ) 2022 eli fessler (frozenpandaman), clovervidia
# Based on splatnet2statink (ↄ) 2017-2022 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3

import argparse, datetime, json, os, shutil, re, requests, sys, time, uuid
import msgpack
import iksm, utils

A_VERSION = "0.1.5"

DEBUG = False

os.system("") # ANSI escape setup
if sys.version_info[1] >= 7: # only works on python 3.7+
	sys.stdout.reconfigure(encoding='utf-8') # note: please stop using git bash

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
	config_file.write(json.dumps(CONFIG_DATA, indent=4, sort_keys=False, separators=(',', ': ')))
	config_file.close()
	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)
	config_file.close()

# SET GLOBALS
API_KEY       = CONFIG_DATA["api_key"]       # for stat.ink
USER_LANG     = CONFIG_DATA["acc_loc"][:5]   # nintendo account info
USER_COUNTRY  = CONFIG_DATA["acc_loc"][-2:]  # nintendo account info
GTOKEN        = CONFIG_DATA["gtoken"]        # for accessing splatnet - base64
BULLETTOKEN   = CONFIG_DATA["bullettoken"]   # for accessing splatnet - base64 json web token
SESSION_TOKEN = CONFIG_DATA["session_token"] # for nintendo login
F_GEN_URL     = CONFIG_DATA["f_gen"]         # endpoint for generating f (imink API by default)

# SET HTTP HEADERS
if "app_user_agent" in CONFIG_DATA:
	APP_USER_AGENT = str(CONFIG_DATA["app_user_agent"])
else:
	APP_USER_AGENT = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) ' \
		'AppleWebKit/537.36 (KHTML, like Gecko) ' \
		'Chrome/94.0.4606.61 Mobile Safari/537.36'

def write_config(tokens):
	'''Writes config file and updates the global variables.'''

	config_file = open(config_path, "w")
	config_file.seek(0)
	config_file.write(json.dumps(tokens, indent=4, sort_keys=False, separators=(',', ': ')))
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


def headbutt():
	'''Return a (dynamic!) header used for GraphQL requests.'''

	graphql_head = {
		'Authorization':    f'Bearer {BULLETTOKEN}', # update every time it's called with current global var
		'Accept-Language':  USER_LANG,
		'User-Agent':       APP_USER_AGENT,
		'X-Web-View-Ver':   utils.get_web_view_ver(),
		'Content-Type':     'application/json',
		'Accept':           '*/*',
		'Origin':           'https://api.lp1.av5ja.srv.nintendo.net',
		'X-Requested-With': 'com.nintendo.znca',
		'Referer':          f'https://api.lp1.av5ja.srv.nintendo.net/?lang={USER_LANG}&na_country={USER_COUNTRY}&na_lang={USER_LANG}',
		'Accept-Encoding':  'gzip, deflate'
	}
	return graphql_head


def prefetch_checks(printout=False):
	'''Queries the SplatNet 3 homepage to check if our gtoken cookie and bulletToken are still valid, otherwise regenerate.'''

	if printout:
		print("Validating your tokens...", end='\r')
	if SESSION_TOKEN == "" or GTOKEN == "" or BULLETTOKEN == "":
		gen_new_tokens("blank")

	sha = utils.translate_rid["HomeQuery"]
	test = requests.post(utils.GRAPHQL_URL, data=utils.gen_graphql_body(sha), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
	if test.status_code != 200:
		if printout:
			print("\n")
		gen_new_tokens("expiry")
	else:
		if printout:
			print("Validating your tokens... done.\n")


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
			sys.exit(0)

	if SESSION_TOKEN == "":
		print("Please log in to your Nintendo Account to obtain your session_token.")
		new_token = iksm.log_in(A_VERSION)
		if new_token is None:
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
		new_bullettoken = iksm.get_bullet(new_gtoken, utils.get_web_view_ver(), APP_USER_AGENT, acc_lang, acc_country)
	CONFIG_DATA["gtoken"] = new_gtoken # valid for 2 hours
	CONFIG_DATA["bullettoken"] = new_bullettoken # valid for 2 hours
	CONFIG_DATA["acc_loc"] = acc_lang + "|" + acc_country
	write_config(CONFIG_DATA)

	if manual_entry:
		print("Wrote tokens to config.txt.\n")
	else:
		print(f"Wrote tokens for {acc_name} to config.txt.\n")


def fetch_json(which, separate=False, exportall=False, specific=False, numbers_only=False, printout=False, skipprefetch=False):
	'''Returns results JSON from SplatNet 3, including a combined dict for ink battles + SR jobs if requested.'''

	swim = SquidProgress()

	if DEBUG:
		print(f"* fetch_json() called with which={which}, separate={separate}, " \
			f"exportall={exportall}, specific={specific}, numbers_only={numbers_only}")

	if exportall and not separate:
		print("fetch_json() must be called with separate=True if using exportall.")
		sys.exit(1)

	if not skipprefetch:
		prefetch_checks(printout)
		if DEBUG:
			print("* prefetch_checks() succeeded")
	swim()

	ink_list, salmon_list = [], []
	parent_files = []

	queries = []
	if which == "both" or which == "ink":
		if specific in (True, "regular"):
			queries.append("RegularBattleHistoriesQuery")
		if specific in (True, "anarchy"):
			queries.append("BankaraBattleHistoriesQuery")
		if specific in (True, "private") and not utils.custom_key_exists("ignore_private", CONFIG_DATA):
			queries.append("PrivateBattleHistoriesQuery")
		else:
			if DEBUG:
				print("* not specific, just looking at latest")
			queries.append("LatestBattleHistoriesQuery")
	else:
		queries.append(None)
	if which in ("both", "salmon"):
		queries.append("CoopHistoryQuery")
	else:
		queries.append(None)

	needs_sorted = False # https://ygdp.yale.edu/phenomena/needs-washed :D

	for sha in queries:
		if sha is not None:
			if DEBUG:
				print(f"* making query1 to {sha}")
			sha = utils.translate_rid[sha]
			battle_ids, job_ids = [], []

			query1 = requests.post(utils.GRAPHQL_URL, data=utils.gen_graphql_body(sha), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
			query1_resp = json.loads(query1.text)
			swim()

			# ink battles - latest 50 of any type
			if "latestBattleHistories" in query1_resp["data"]:
				for battle_group in query1_resp["data"]["latestBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"]) # don't filter out private battles here - do that in post_result()

			# ink battles - latest 50 turf war
			elif "regularBattleHistories" in query1_resp["data"]:
				needs_sorted = True
				for battle_group in query1_resp["data"]["regularBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"])
			# ink battles - latest 50 anarchy battles
			elif "bankaraBattleHistories" in query1_resp["data"]:
				needs_sorted = True
				for battle_group in query1_resp["data"]["bankaraBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"])
			# ink battles - latest 50 private battles
			elif "privateBattleHistories" in query1_resp["data"] \
			and not utils.custom_key_exists("ignore_private", CONFIG_DATA):
				needs_sorted = True
				for battle_group in query1_resp["data"]["privateBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"])
			# salmon run jobs - latest 50
			elif "coopResult" in query1_resp["data"]:
				for shift in query1_resp["data"]["coopResult"]["historyGroups"]["nodes"]:
					for job in shift["historyDetails"]["nodes"]:
						job_ids.append(job["id"])

			if numbers_only:
				ink_list.extend(battle_ids)
				salmon_list.extend(job_ids)
			else: # ALL DATA - TAKES A LONG TIME
				for bid in battle_ids:
					query2_b = requests.post(utils.GRAPHQL_URL,
						data=utils.gen_graphql_body(utils.translate_rid["VsHistoryDetailQuery"], "vsResultId", bid),
						headers=headbutt(),
						cookies=dict(_gtoken=GTOKEN))
					query2_resp_b = json.loads(query2_b.text)
					ink_list.append(query2_resp_b)
					swim()

				for jid in job_ids:
					query2_j = requests.post(utils.GRAPHQL_URL,
						data=utils.gen_graphql_body(utils.translate_rid["CoopHistoryDetailQuery"], "coopHistoryDetailId", jid),
						headers=headbutt(),
						cookies=dict(_gtoken=GTOKEN))
					query2_resp_j = json.loads(query2_j.text)
					salmon_list.append(query2_resp_j)
					swim()

				if needs_sorted: # put regular, bankara, and private in order, since they were exported in sequential chunks
					try:
						ink_list = [x for x in ink_list if x['data']['vsHistoryDetail'] is not None] # just in case
						ink_list = sorted(ink_list, key=lambda d: d['data']['vsHistoryDetail']['playedTime'])
					except:
						print("(!) Exporting without sorting results.json")
					try:
						salmon_list = [x for x in salmon_list if x['data']['coopHistoryDetail'] is not None]
						salmon_list = sorted(salmon_list, key=lambda d: d['data']['coopHistoryDetail']['playedTime'])
					except:
						print("(!) Exporting without sorting coop_results.json")
			parent_files.append(query1_resp)
		else: # sha = None (we don't want to get the specified result type)
			pass

	if exportall:
		return parent_files, ink_list, salmon_list
	else:
		if separate:
			return ink_list, salmon_list
		else:
			combined = ink_list + salmon_list
			return combined


def update_salmon_profile():
	''' Updates stat.ink Salmon Run stats/profile.'''

	pass

	# prefetch_checks()

	# old code - need stat.ink s3 support - TODO
	# url = nintendo's api/coop_results...
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

	# url = "https://stat.ink/api/v2/salmon-stats" # TODO - need stat.ink s3 support
	# auth = {'Authorization': f'Bearer {API_KEY}'}
	# updateprofile = requests.post(url, headers=auth, data=payload)

	# if updateprofile.ok:
	# 	print("Successfully updated your Salmon Run profile.")
	# else:
	# 	print("Could not update your Salmon Run profile. Error from stat.ink:")
	# 	print(updateprofile.text)


def set_scoreboard(battle):
	'''Returns two lists of player dictionaries, for our_team_players and their_team_players.'''

	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Post-v3-battle#player-structure
	our_team_players, their_team_players = [], []

	for i, player in enumerate(battle["myTeam"]["players"]):
		p_dict = {}
		p_dict["me"]              = "yes" if player["isMyself"] else "no"
		p_dict["name"]            = player["name"]
		try:
			p_dict["number"]      = str(player["nameId"]) # splashtag # - can contain alpha chars too... (why!!!)
		except KeyError: # may not be present if first battle as "Player"
			pass
		p_dict["splashtag_title"] = player["byname"] # splashtag title
		p_dict["weapon"]          = utils.b64d(player["weapon"]["id"])
		p_dict["inked"]           = player["paint"]
		p_dict["rank_in_team"]    = i+1
		if "result" in player and player["result"] is not None:
			p_dict["kill_or_assist"] = player["result"]["kill"]
			p_dict["assist"]         = player["result"]["assist"]
			p_dict["kill"]           = p_dict["kill_or_assist"] - p_dict["assist"]
			p_dict["death"]          = player["result"]["death"]
			p_dict["special"]        = player["result"]["special"]
			p_dict["disconnected"]   = "no"
		else:
			p_dict["disconnected"]   = "yes"
		our_team_players.append(p_dict)

	for i, player in enumerate(battle["otherTeams"][0]["players"]): # no support for tricolor TW yet
		p_dict = {}
		p_dict["me"]              = "no"
		p_dict["name"]            = player["name"]
		try:
			p_dict["number"]      = str(player["nameId"])
		except:
			pass
		p_dict["splashtag_title"] = player["byname"]
		p_dict["weapon"]          = utils.b64d(player["weapon"]["id"])
		p_dict["inked"]           = player["paint"]
		p_dict["rank_in_team"]    = i+1
		if "result" in player and player["result"] is not None:
			p_dict["kill_or_assist"] = player["result"]["kill"]
			p_dict["assist"]         = player["result"]["assist"]
			p_dict["kill"]           = p_dict["kill_or_assist"] - p_dict["assist"]
			p_dict["death"]          = player["result"]["death"]
			p_dict["special"]        = player["result"]["special"]
			p_dict["disconnected"]   = "no"
		else:
			p_dict["disconnected"]   = "yes"
		their_team_players.append(p_dict)

	return our_team_players, their_team_players


def prepare_battle_result(battle, ismonitoring, overview_data=None):
	'''Converts the Nintendo JSON format for a Turf War/Ranked battle to the stat.ink one.'''

	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Post-v3-battle
	payload = {}
	battle = battle["vsHistoryDetail"]

	## UUID ##
	##########
	full_id = utils.b64d(battle["id"])
	payload["uuid"] = str(uuid.uuid5(utils.S3S_NAMESPACE, full_id[-52:])) # input format: <YYYYMMDD>T<HHMMSS>_<uuid>

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
	elif mode == "FEST":
		# if utils.b64d(battle["vsMode"]["id"]) == 6:
			# payload["lobby"] = "fest_open"
		# elif  utils.b64d(battle["vsMode"]["id"]) == 7:
			# payload["lobby"] = "fest_pro"
		print("Splatfest battles are not yet supported - skipping. ")
		return {}

	## RULE ##
	##########
	rule = battle["vsRule"]["rule"]
	if rule == "TURF_WAR":
		payload["rule"] = "nawabari" # could be splatfest too
	elif rule == "AREA":
		payload["rule"] = "area"
	elif rule == "LOFT":
		payload["rule"] = "yagura"
	elif rule == "GOAL":
		payload["rule"] = "hoko"
	elif rule == "CLAM":
		payload["rule"] = "asari"
	# elif rule == "TRI_COLOR":
		# payload["rule"] = "..."

	## STAGE ##
	###########
	# hardcoded before first major game update
	stage_id = utils.b64d(battle["vsStage"]["id"])
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

	## WEAPON, K/D/A/S, TURF INKED ##
	#################################
	for i, player in enumerate(battle["myTeam"]["players"]): # specified again in set_scoreboard()
		if player["isMyself"] == True:
			payload["weapon"]         = utils.b64d(player["weapon"]["id"])
			payload["inked"]          = player["paint"]
			payload["species"]        = player["species"].lower() # not supported for now
			payload["rank_in_team"]   = i+1
			# ...        = player["result"]["festDragonCert"] NONE, DRAGON, or DOUBLE_DRAGON - splatfest
			if player["result"] is not None: # null if player disconnect
				payload["kill_or_assist"] = player["result"]["kill"]
				payload["assist"]         = player["result"]["assist"]
				payload["kill"]           = payload["kill_or_assist"] - payload["assist"]
				payload["death"]          = player["result"]["death"]
				payload["special"]        = player["result"]["special"]
				# ...        = player["result"]["noroshiTry"] = ultra signal attempts - splatfest
				break

	## RESULT ##
	############
	result = battle["judgement"]
	if result == "WIN":
		payload["result"] = "win"
	elif result in ("LOSE", "DEEMED_LOSE"):
		payload["result"] = "lose"
	elif result == "EXEMPTED_LOSE":
		payload["result"] = "exempted_lose" # doesn't count toward stats
	elif result == "DRAW":
		payload["result"] = "draw"

	## START/END TIMES ##
	#####################
	payload["start_at"] = utils.epoch_time(battle["playedTime"])
	payload["end_at"]   = payload["start_at"] + battle["duration"]

	## SCOREBOARD ##
	################
	payload["our_team_players"], payload["their_team_players"] = set_scoreboard(battle)

	## SPLATFEST ##
	###############
	# if mode == "FEST":
		# battle["festMatch"]["dragonMatchType"] - NORMAL (1x), DECUPLE (10x), DRAGON (100x), DOUBLE_DRAGON (333x)
		# battle["festMatch"]["contribution"] # clout
		# battle["festMatch"]["jewel"]
		# battle["festMatch"]["myFestPower"] # pro only
		# if rule == "TRI_COLOR":
			# ...

	# Turf War only (NOT TRICOLOR)
	if mode == "REGULAR":
		try:
			payload["our_team_percent"]   = float(battle["myTeam"]["result"]["paintRatio"]) * 100
			payload["their_team_percent"] = float(battle["otherTeams"][0]["result"]["paintRatio"]) * 100
		except TypeError: # draw - 'result' is null
			pass

		our_team_inked, their_team_inked = 0, 0
		for player in battle["myTeam"]["players"]:
			our_team_inked += player["paint"]
		for player in battle["otherTeams"][0]["players"]:
			their_team_inked += player["paint"]
		payload["our_team_inked"] = our_team_inked
		payload["their_team_inked"] = their_team_inked

	# Anarchy Battles only
	if mode == "BANKARA":

		try:
			payload["our_team_count"]   = battle["myTeam"]["result"]["score"]
			payload["their_team_count"] = battle["otherTeams"][0]["result"]["score"]
		except TypeError: # draw - 'result' is null
			pass

		payload["knockout"] = "no" if battle["knockout"] is None or battle["knockout"] == "NEITHER" else "yes"
		payload["rank_exp_change"] = battle["bankaraMatch"]["earnedUdemaePoint"]

		if overview_data or ismonitoring: # if we're passing in the overview.json file with -i, or monitoring mode
			if overview_data is None:
				overview_post = requests.post(utils.GRAPHQL_URL,
					data=utils.gen_graphql_body(utils.translate_rid["BankaraBattleHistoriesQuery"]),
					headers=headbutt(),
					cookies=dict(_gtoken=GTOKEN))
				overview_data = [json.loads(overview_post.text)] # make the request in real-time when monitoring to get rank, etc.
			for screen in overview_data:
				if "bankaraBattleHistories" in screen["data"]:
					ranked_list = screen["data"]["bankaraBattleHistories"]["historyGroups"]["nodes"]
					break
				elif "latestBattleHistories" in screen["data"]: # early exports used this, and no bankaraMatchChallenge below
					ranked_list = screen["data"]["latestBattleHistories"]["historyGroups"]["nodes"]
					break
			for parent in ranked_list: # groups in overview (ranked) JSON/screen
				for idx, child in enumerate(parent["historyDetails"]["nodes"]):

					if child["id"] == battle["id"]: # found the battle ID in the other file

						full_rank = re.split('([0-9]+)', child["udemae"].lower())
						payload["rank_before"] = full_rank[0]
						if len(full_rank) > 1:
							payload["rank_before_s_plus"] = int(full_rank[1])

						# anarchy battle (series) - not open
						if "bankaraMatchChallenge" in parent and parent["bankaraMatchChallenge"] is not None:

							# rankedup = parent["bankaraMatchChallenge"]["isUdemaeUp"]
							ranks = ["c-", "c", "c+", "b-", "b", "b+", "a-", "a", "a+", "s"] # s+ handled separately

							# rank-up battle
							if parent["bankaraMatchChallenge"]["isPromo"] == True:
								payload["rank_up_battle"] = "yes"
							else:
								payload["rank_up_battle"] = "no"

							if parent["bankaraMatchChallenge"]["udemaeAfter"] is None:
								payload["rank_after"] = payload["rank_before"]
							else:
								if idx != 0:
									payload["rank_after"] = payload["rank_before"]
								else: # the battle where we actually ranked up
									full_rank_after = re.split('([0-9]+)', parent["bankaraMatchChallenge"]["udemaeAfter"].lower())
									payload["rank_after"] = full_rank_after[0]
									if len(full_rank_after) > 1:
										payload["rank_after_s_plus"] = int(full_rank_after[1])

							if idx == 0: # for the last battle in the series only
								# send overall win/lose count
								payload["challenge_win"] = parent["bankaraMatchChallenge"]["winCount"]
								payload["challenge_lose"] = parent["bankaraMatchChallenge"]["loseCount"]

								# send exp change (gain)
								if payload["rank_exp_change"] is None:
									payload["rank_exp_change"] = parent["bankaraMatchChallenge"]["earnedUdemaePoint"]

							if DEBUG:
								print(f'* {battle["myTeam"]["judgement"]} {idx}')
								print(f'* rank_before: {payload["rank_before"]}')
								print(f'* rank_after: {payload["rank_after"]}')
								print(f'* rank up battle: {parent["bankaraMatchChallenge"]["isPromo"]}')
								print(f'* is ranked up: {parent["bankaraMatchChallenge"]["isUdemaeUp"]}')
								if idx == 0:
									print(f'* rank_exp_change: {parent["bankaraMatchChallenge"]["earnedUdemaePoint"]}')
								else:
									print(f'* rank_exp_change: 0')

						break # found the child ID, no need to continue

	## MEDALS ##
	############
	medals = []
	for medal in battle["awards"]:
		medals.append(medal["name"])
	payload["medals"] = medals

	## SCREENSHOTS ##
	#################
	# TODO - change to require -ss option?
	# im = utils_ss.screenshot(battle["id"])

	# scoreboard
	# payload["image_result"] = BytesIO(im.content).getvalue()

	# gear
	# payload["image_gear"] = ...

	# no way to get: level_beforea/after, cash_before/after, rank_after_exp

	payload["automated"] = "yes" # data was not manually entered!
	payload["splatnet_json"] = json.dumps(battle)

	return payload


def prepare_job_result(battle, ismonitoring, overview_data=None):
	'''Converts the Nintendo JSON format for a Salmon Run job to the stat.ink one.'''

	pass # stat.ink doesn't support SR yet
	# combo of set_teammates() + salmon_post_shift()
	# set payload["splatnet_json"]


def post_result(data, ismonitoring, isblackout, istestrun, overview_data=None):
	'''Uploads battle/job JSON to stat.ink, and prints the returned URL or error message..'''

	if isinstance(data, list): # -o export format
		try:
			data = [x for x in data if x['data']['vsHistoryDetail'] is not None] # avoid {'data': {'vsHistoryDetail': None}} error
			results = sorted(data, key=lambda d: d['data']['vsHistoryDetail']['playedTime'])
		except KeyError:
			try:
				data = [x for x in data if x['coopHistoryDetail'] is not None]
				results = sorted(data, key=lambda d: d['data']['coopHistoryDetail']['playedTime'])
			except KeyError: # unsorted - shouldn't happen
				print("(!) Uploading without chronologically sorting results")
				results = data
	elif isinstance(data, dict):
		try:
			results = data["results"]
		except KeyError:
			results = [data] # single battle/job - make into a list

	# filter down to one battle at a time
	for i in range(len(results)):
		if "vsHistoryDetail" in results[i]["data"]: # ink battle
			payload = prepare_battle_result(results[i]["data"], ismonitoring, overview_data)
		elif "coopHistoryDetail" in results[i]["data"]: # salmon run job
			payload = prepare_job_result(results[i]["data"], ismonitoring, overview_data)
		else: # shouldn't happen
			print("Ill-formatted JSON while uploading. Exiting.")
			print('results[i]["data"]:')
			print(results[i]["data"])
			sys.exit(1)

		if len(payload) == 0: # received blank payload from prepare_job_result() - skip unsupported battle
			continue

		# should have been taken care of in fetch_json() but just in case...
		if payload["lobby"] == "private" and utils.custom_key_exists("ignore_private", CONFIG_DATA): # TODO - also check SR?
			continue

		# TODO - isblackout stuff... for SR too

		s3s_values = {'agent': '\u0073\u0033\u0073', 'agent_version': f'v{A_VERSION}'} # lol
		s3s_values["agent_variables"] = {'Upload Mode': "Monitoring" if ismonitoring else "Manual"}
		payload.update(s3s_values)

		if payload["agent"][0:3] != os.path.basename(__file__)[:-3]:
			print("Could not upload. Please contact @frozenpandaman on GitHub for assistance.")
			sys.exit(0)

		if istestrun:
			payload["test"] = "yes"

		# post
		url = "https://stat.ink/api/v3/battle"
		auth = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/x-msgpack'}
		postbattle = requests.post(url, headers=auth, data=msgpack.packb(payload), allow_redirects=False)

		# response
		headerloc = postbattle.headers.get('location')
		time_now = int(time.time())
		try:
			time_uploaded = json.loads(postbattle.text)["created_at"]["time"]
		except KeyError:
			time_uploaded = None
		except json.decoder.JSONDecodeError: # retry once
			postbattle = requests.post(url, headers=auth, data=msgpack.packb(payload), allow_redirects=False)
			headerloc = postbattle.headers.get('location')
			time_now = int(time.time())
			try:
				time_uploaded = json.loads(postbattle.text)["created_at"]["time"]
			except:
				print("Error with stat.ink. Please try again.")

		if DEBUG:
			print(f"* time uploaded: {time_uploaded}; time now: {time_now}")

		if postbattle.status_code != 201: # Created (or already exists)
			print("Error uploading battle. Message from server:")
			print(postbattle.content.decode('utf-8'))
		elif time_uploaded <= time_now - 5: # give some leeway
			print(f"Battle already uploaded - {headerloc}")
		else: # 200 OK
			print(f"Battle uploaded to {headerloc}")


def check_for_updates():
	'''Checks the script version against the repo, reminding users to update if available.'''

	print('\033[3m' + "» While s3s is in beta, please update the script regularly via " \
		'`\033[91m' + "git pull" + '\033[0m' + "`." + '\033[0m' + "\n")
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

	noun = utils.set_noun(which)
	try:
		if which == "ink":
			print("Note: 50 recent battles of each type (up to 150 total) may be uploaded by instead manually exporting data with " \
				'\033[91m' + "-o" + '\033[0m' + ".\n")
		n = int(input(f"Number of recent {noun} to upload (0-50)? "))
	except ValueError:
		print("Please enter an integer between 0 and 50. Exiting.")
		sys.exit(0)
	if n < 1:
		print("Exiting without uploading anything.")
		sys.exit(0)
	elif n > 50:
		if which == "salmon":
			print("SplatNet 3 only stores the 50 most recent jobs. Exiting.")
		elif which == "ink":
			print("\nIn this mode, s3s can only fetch the 50 most recent battles (of any type) at once. " \
				"To export & upload the 50 most recent battles of each type " \
				"(Regular, Anarchy, and Private) for up to 150 results total, run the script with " \
				'\033[91m' + "-o" + '\033[0m' + " and then " \
				'\033[91m' + "-i results.json overview.json" + '\033[0m' + ".")
		sys.exit(0)
	else:
		return n


def fetch_and_upload_single_result(hash, noun, ismonitoring, isblackout, istestrun):
	'''Perform a GraphQL request for a single vsResultId/coopResultId and call post_result().'''

	if noun in ("battles", "battle"):
		dict_key  = "VsHistoryDetailQuery"
		dict_key2 = "vsResultId"
	else: # noun == "jobs" or "job"
		dict_key  = "CoopHistoryQuery"
		dict_key2 = "coopResultId"

	result_post = requests.post(utils.GRAPHQL_URL,
			data=utils.gen_graphql_body(utils.translate_rid[dict_key], dict_key2, hash),
			headers=headbutt(),
			cookies=dict(_gtoken=GTOKEN))
	result = json.loads(result_post.text)
	post_result(result, ismonitoring, isblackout, istestrun)


def check_if_missing(which, ismonitoring, isblackout, istestrun):
	'''Checks for unuploaded battles, and uploads any that are found.'''

	noun = utils.set_noun(which)
	print(f"Checking if there are previously-unuploaded {noun}...")

	urls = []
	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Get-UUID-List-(for-s3s)
	if which in ("both", "ink"):
		urls.append("https://stat.ink/api/v3/s3s/uuid-list") # max 200 entries
	else:
		urls.append(None)
	# if which == "both" or which == "salmon":
		# urls.append("...")
	# else:
		# urls.append(None)

	noun = "battles" # first (and maybe only)
	which = "ink"
	for url in urls:
		if url is not None:
			printed = False
			auth = {'Authorization': f'Bearer {API_KEY}'}
			resp = requests.get(url, headers=auth) # no params = all: regular, bankara, private
			try:
				statink_uploads = json.loads(resp.text)
			except:
				print(f"Encountered an error while checking recently-uploaded {noun}. Is stat.ink down?")
				sys.exit(1)

			# ! fetch from online
			splatnet_ids = fetch_json(which, specific=True, numbers_only=True) # 'specific' - check ALL possible battles

			# same as code in -i section below...
			for id in reversed(splatnet_ids):
				full_id = utils.b64d(id)
				old_uuid = full_id[-36:]
				new_uuid = str(uuid.uuid5(utils.S3S_NAMESPACE, full_id[-52:]))

				if new_uuid in statink_uploads:
					continue
				if old_uuid in statink_uploads:
					if not utils.custom_key_exists("force_uploads", CONFIG_DATA):
						continue
				if not printed:
					printed = True
					print(f"Previously-unuploaded {noun} detected. Uploading now...")

				fetch_and_upload_single_result(id, noun, ismonitoring, isblackout, istestrun)

			if not printed:
				print(f"No previously-unuploaded {noun} found.")

		noun = "jobs" # for second run through the loop
		which = "salmon"


def monitor_battles(which, secs, isblackout, istestrun):
	'''Monitors JSON for changes/new battles and uploads them.'''

	if DEBUG:
		print(f"* monitoring mode start - calling fetch_json() w/ which={which}")
	# ! fetch from online - no 'specific' = should all be within 'latest'
	cached_battles, cached_jobs = fetch_json(which, separate=True, numbers_only=True, printout=True)
	if DEBUG:
		print("* got battle numbers")

	cached_battles.reverse()
	cached_jobs.reverse()

	# counters
	battle_wins, battle_losses, battle_draws = [0]*3 # init all to 0
	splatfest_wins, splatfest_losses, splatfest_draws, mirror_matches = [0]*4
	job_successes, job_failures = [0]*2

	mins = str(round(float(secs)/60.0, 2))
	mins = mins[:-2] if mins[-2:] == ".0" else mins
	print(f"Waiting for new {utils.set_noun(which)}... (checking every {mins} minutes)")

	try:
		while True:
			for i in range(secs, -1, -1):
				sys.stdout.write(f"Press Ctrl+C to exit. {i} ")
				sys.stdout.flush()
				time.sleep(1)
				sys.stdout.write("\r")

			print("Checking for new results...", end='\r')
			# ! fetch from online
			ink_results, salmon_results = fetch_json(which, separate=True, numbers_only=True) # only numbers or it'd take a long time

			if which in ("both", "ink"):
				for num in reversed(ink_results):
					if num not in cached_battles:
						# get the full battle data
						result_post = requests.post(utils.GRAPHQL_URL,
							data=utils.gen_graphql_body(utils.translate_rid["VsHistoryDetailQuery"], "vsResultId", num),
							headers=headbutt(),
							cookies=dict(_gtoken=GTOKEN))
						result = json.loads(result_post.text)

						if result["data"]["vsHistoryDetail"]["vsMode"]["mode"] == "PRIVATE" \
						and utils.custom_key_exists("ignore_private", CONFIG_DATA):
							pass
						else:
							if result["data"]["vsHistoryDetail"]["myTeam"]["judgement"] == "WIN":
								outcome = "Victory"
							elif result["data"]["vsHistoryDetail"]["myTeam"]["judgement"] == "LOSE":
								outcome = "Defeat"
							else:
								outcome = "Draw"
							splatfest_match = True if result["data"]["vsHistoryDetail"]["vsMode"]["mode"] == "FEST" else False
							if splatfest_match: # keys will exist
								our_team_name = result["data"]["vsHistoryDetail"]["myTeam"]["festTeamName"]
								their_team_name = result["data"]["vsHistoryDetail"]["otherTeams"][0]["festTeamName"] # no tricolor support
								mirror_match = True if our_team_name == their_team_name else False
							if outcome == "Victory":
								battle_wins += 1
								if splatfest_match and not mirror_match:
									splatfest_wins += 1
							elif outcome == "Defeat":
								battle_losses += 1
								if splatfest_match and not mirror_match:
									splatfest_losses += 1
							else:
								battle_draws += 1
								if splatfest_match and not mirror_match:
									splatfest_draws += 1
							if splatfest_match and mirror_match:
								mirror_matches += 1

							stagename = result["data"]["vsHistoryDetail"]["vsStage"]["name"]
							shortname = stagename.split(" ")[-1]
							endtime = utils.epoch_time(result["data"]["vsHistoryDetail"]["playedTime"]) + \
								result["data"]["vsHistoryDetail"]["duration"]
							dt = datetime.datetime.fromtimestamp(endtime).strftime('%I:%M:%S %p').lstrip("0")

							print(f"New battle result detected at {dt}! ({shortname}, {outcome})")
						cached_battles.append(num)
						post_result(result, True, isblackout, istestrun) # True = is monitoring mode

			if which in ("both", "salmon"):
				for num in reversed(salmon_results):
					if num not in cached_jobs:
						# get the full job data
						result_post = requests.post(utils.GRAPHQL_URL,
							data=utils.gen_graphql_body(utils.translate_rid["CoopHistoryDetailQuery"], "coopResultId", num),
							headers=headbutt(),
							cookies=dict(_gtoken=GTOKEN))
						result = json.loads(result_post.text)

						if False and utils.custom_key_exists("ignore_private"): # TODO - how to check for SR private battles?
							pass
						else:
							outcome = "Success" if result["job_result"]["is_clear"] == True else "Failure"
							if outcome == "Success":
								job_successes += 1
							else: # Failure
								job_failures += 1

							stagename = result["data"]["coopHistoryDetail"]["coopStage"]["name"]
							shortname = stagename.split(" ")[-1] # fine for salmon run stage names too
							endtime = utils.epoch_time(result["data"]["coopHistoryDetail"]["playedTime"]) + \
								result["data"]["coopHistoryDetail"]["duration"]

							dt = datetime.datetime.fromtimestamp(endtime).strftime('%I:%M:%S %p').lstrip("0")
							print(f"New job result detected at {dt}! ({shortname}, {outcome})")
							cached_jobs.append(num)
							post_result(result, True, isblackout, istestrun) # True = is monitoring mode

	except KeyboardInterrupt:
		# print(f"\nChecking to see if there are unuploaded {utils.set_noun(which)} before exiting...") # TODO

		# TODO - do update_salmon_profile() at end if salmon run
		print("\n\nChecking for unuploaded results before exiting is not yet implemented.")
		print("Please run s3s again with " + '\033[91m' + "-r" + '\033[0m' + " to get these battles.")
		print("Bye!")


class SquidProgress:
	'''Display animation while waiting.'''

	def __init__(self):
		self.count = 0

	def __call__(self):
		lineend = shutil.get_terminal_size()[0] - 5 # 5 = ('>=> ' or '===>') + blank 1
		ika = '>=> ' if self.count % 2 == 0 else '===>'
		sys.stdout.write(f"\r{' '*self.count}{ika}{' '*(lineend - self.count)}")
		sys.stdout.flush()
		self.count += 1
		if self.count > lineend:
			self.count = 0

	def __del__(self):
		sys.stdout.write(f"\r{' '*(shutil.get_terminal_size()[0] - 1)}\r")
		sys.stdout.flush()


def main():
	'''Main process, including I/O and setup.'''

	print('\033[93m\033[1m' + "s3s" + '\033[0m\033[93m' + f" v{A_VERSION}" + '\033[0m')

	# setup
	#######
	check_for_updates()
	check_statink_key()

	# argparse stuff
	################
	parser = argparse.ArgumentParser()
	srgroup = parser.add_mutually_exclusive_group()
	parser.add_argument("-M", dest="N", required=False, nargs="?", action="store",
		help="monitoring mode; pull data every N secs (default: 300)", const=300)
	parser.add_argument("-r", required=False, action="store_true",
		help="retroactively post unuploaded battles/jobs")
	srgroup.add_argument("-nsr", required=False, action="store_true",
						help="do not check for Salmon Run jobs")
	srgroup.add_argument("-osr", required=False, action="store_true",
						help="only check for Salmon Run jobs")
	# parser.add_argument("--blackout", required=False, action="store_true",
		# help="black out names on scoreboard result images")
	parser.add_argument("-o", required=False, action="store_true",
		help="export all possible results to local files")
	parser.add_argument("-i", dest="file", nargs=2, required=False,
		help="upload local results. use `-i results.json overview.json`")
	parser.add_argument("-t", required=False, action="store_true",
		help="dry run for testing (won't post to stat.ink)")
	parser_result = parser.parse_args()

	# regular args
	n_value     = parser_result.N
	check_old   = parser_result.r
	only_ink    = parser_result.nsr # ink battles ONLY
	only_salmon = parser_result.osr # salmon run ONLY
	# blackout    = parser_result.blackout
	blackout = False

	# testing/dev stuff
	test_run  = parser_result.t
	filenames = parser_result.file # intended for results.json AND overview.json
	outfile   = parser_result.o # output to local files

	# i/o checks
	############
	if only_ink and only_salmon:
		print("That doesn't make any sense! :) Exiting.")
		sys.exit(0)

	elif outfile and len(sys.argv) > 2:
		print("Cannot use -o with other arguments. Exiting.")
		sys.exit(0)

	secs = -1
	if n_value is not None:
		try:
			secs = int(parser_result.N)
		except ValueError:
			print("Number provided must be an integer. Exiting.")
			sys.exit(0)
		if secs < 0:
			print("No.")
			sys.exit(0)
		elif secs < 60:
			print("Minimum number of seconds in monitoring mode is 60. Exiting.")
			sys.exit(0)

	# export results to file: -o
	############################
	if outfile:
		prefetch_checks(printout=True)
		print("Fetching your JSON files to export locally. This might take a while...")
		# fetch_json() calls prefetch_checks() to gen or check tokens
		parents, results, coop_results = fetch_json("both", separate=True, exportall=True, specific=True, skipprefetch=True)

		cwd = os.getcwd()
		export_dir = os.path.join(cwd, f'export-{int(time.time())}')
		if not os.path.exists(export_dir):
			os.makedirs(export_dir)

		print()
		if parents is not None:
			with open(os.path.join(cwd, export_dir, "overview.json"), "x") as fout:
				json.dump(parents, fout)
				print("Created overview.json with general info about your battle and job stats.")

		if results is not None:
			with open(os.path.join(cwd, export_dir, "results.json"), "x") as fout:
				json.dump(results, fout)
				print("Created results.json with detailed recent battle stats (up to 50 of each type).")

		if coop_results is not None:
			with open(os.path.join(cwd, export_dir, "coop_results.json"), "x") as fout:
				json.dump(coop_results, fout)
				print("Created coop_results.json with detailed recent Salmon Run job stats (up to 50).")

		print("\nHave fun playing Splatoon 3! :) Bye!")
		sys.exit(0)

	# manual json upload: -i
	########################
	if filenames: # 2 files in list
		if os.path.basename(filenames[0]) != "results.json" or os.path.basename(filenames[1]) != "overview.json":
			print("Must use the format " \
				'\033[91m' + "-i path/to/results.json path/to/overview.json" + '\033[0m' + ".")
			sys.exit(1)
		for filename in filenames:
			if not os.path.exists(filename):
				print(f"File {filename} does not exist!") # exit
				sys.exit(1)
		with open(filenames[0]) as data_file:
			try:
				data = json.load(data_file)
			except ValueError:
				print("Could not decode JSON object in results.json.")
				sys.exit(1)
		with open(filenames[1]) as data_file:
			try:
				overview_file = json.load(data_file)
			except ValueError:
				print("Could not decode JSON object in overview.json.")
				sys.exit(1)
		data.reverse()

		# only upload unuploaded results
		auth = {'Authorization': f'Bearer {API_KEY}'}
		resp = requests.get("https://stat.ink/api/v3/s3s/uuid-list", headers=auth)
		try:
			statink_uploads = json.loads(resp.text)
		except:
			print(f"Encountered an error while checking recently-uploaded {noun}. Is stat.ink down?")
			sys.exit(1)

		to_upload = []
		for battle in data:
			if battle["data"]["vsHistoryDetail"] is not None:
				full_id = utils.b64d(battle["data"]["vsHistoryDetail"]["id"])
				old_uuid = full_id[-36:] # not unique because nintendo hates us
				new_uuid = str(uuid.uuid5(utils.S3S_NAMESPACE, full_id[-52:]))

				if new_uuid in statink_uploads:
					print("Skipping already-uploaded battle.")
					continue
				if old_uuid in statink_uploads:
					if not utils.custom_key_exists("force_uploads", CONFIG_DATA):
						print("Skipping already-uploaded battle.")
						continue
				to_upload.append(battle)

		post_result(to_upload, False, blackout, test_run, overview_data=overview_file) # one or multiple; monitoring mode = False
		sys.exit(0)

	# regular run
	#############
	which = "ink" if only_ink else "salmon" if only_salmon else "both"

	# ---
	# TEMP.
	if only_salmon:
		print("stat.ink does not support uploading Salmon Run data at this time. Exiting.")
		sys.exit(0)

	print('\033[96m' + "Uploading battles to stat.ink is now supported!" + '\033[0m' \
		" To save your battle & job data to local files, run the script with the " \
		'\033[91m' + "-o" + '\033[0m' + " flag; to upload your previously exported results, use " \
		'\033[91m' + "-i results.json overview.json" + '\033[0m' + ". " \
		"Or, run the script in monitoring mode (with " + '\033[91m' + "-M" + '\033[0m' \
		") to capture & upload new results as you play. " \
		"stat.ink does not support Salmon Run data (coop_results.json) or Splatfest battles at this time.\n")
	# ---

	if which in ("salmon", "both"):
		update_salmon_profile()

	if check_old:
		check_if_missing(which, True if secs != -1 else False, blackout, test_run)

	if secs != -1: # monitoring mode
		monitor_battles(which, secs, blackout, test_run)

	if not check_old: # regular mode (no -M) and did not just use -r
		if which == "both":
			print("Please specify whether you want to upload battle results (-nsr) or Salmon Run jobs (-osr). Exiting.")
			sys.exit(0)

		n = get_num_results(which)
		print("Pulling data from online...")

		# ! fetch from online
		results = fetch_json(which, numbers_only=True, printout=True)

		results = results[:n] # limit to n uploads
		results.reverse() # sort from oldest to newest
		noun = utils.set_noun(which)
		for hash in results:
			fetch_and_upload_single_result(hash, noun, False, blackout, test_run) # monitoring mode = False


if __name__ == "__main__":
	main()
