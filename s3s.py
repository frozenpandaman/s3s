#!/usr/bin/env python
# s3s (ↄ) 2022-2024 eli fessler (frozenpandaman), clovervidia
# Based on splatnet2statink (ↄ) 2017-2024 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3

import argparse, base64, datetime, json, os, shutil, re, sys, time, uuid
from concurrent.futures import ThreadPoolExecutor
from subprocess import call
import requests, msgpack
from packaging import version
import iksm, utils

A_VERSION = "0.6.7"

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
USER_LANG     = CONFIG_DATA["acc_loc"][:5]   # user input
USER_COUNTRY  = CONFIG_DATA["acc_loc"][-2:]  # nintendo account info
GTOKEN        = CONFIG_DATA["gtoken"]        # for accessing splatnet - base64 json web token
BULLETTOKEN   = CONFIG_DATA["bullettoken"]   # for accessing splatnet - base64
SESSION_TOKEN = CONFIG_DATA["session_token"] # for nintendo login
F_GEN_URL     = CONFIG_DATA["f_gen"]         # endpoint for generating f (imink API by default)

thread_pool = ThreadPoolExecutor(max_workers=2)

# SET HTTP HEADERS
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Linux; Android 14; Pixel 7a) ' \
						'AppleWebKit/537.36 (KHTML, like Gecko) ' \
						'Chrome/120.0.6099.230 Mobile Safari/537.36'
APP_USER_AGENT = str(CONFIG_DATA.get("app_user_agent", DEFAULT_USER_AGENT))


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


def headbutt(forcelang=None):
	'''Returns a (dynamic!) header used for GraphQL requests.'''

	if forcelang:
		lang    = forcelang
		country = forcelang[-2:]
	else:
		lang    = USER_LANG
		country = USER_COUNTRY

	graphql_head = {
		'Authorization':    f'Bearer {BULLETTOKEN}', # update every time it's called with current global var
		'Accept-Language':  lang,
		'User-Agent':       APP_USER_AGENT,
		'X-Web-View-Ver':   iksm.get_web_view_ver(),
		'Content-Type':     'application/json',
		'Accept':           '*/*',
		'Origin':           iksm.SPLATNET3_URL,
		'X-Requested-With': 'com.nintendo.znca',
		'Referer':          f'{iksm.SPLATNET3_URL}?lang={lang}&na_country={country}&na_lang={lang}',
		'Accept-Encoding':  'gzip, deflate'
	}
	return graphql_head


def prefetch_checks(printout=False):
	'''Queries the SplatNet 3 homepage to check if our gtoken & bulletToken are still valid and regenerates them if not.'''

	if printout:
		print("Validating your tokens...", end='\r')

	iksm.get_web_view_ver() # setup

	if SESSION_TOKEN == "" or GTOKEN == "" or BULLETTOKEN == "":
		gen_new_tokens("blank")

	sha = utils.translate_rid["HomeQuery"]
	test = requests.post(iksm.GRAPHQL_URL, data=utils.gen_graphql_body(sha, "naCountry", USER_COUNTRY), headers=headbutt(), cookies=dict(_gtoken=GTOKEN))
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
			print("Blank token(s).          ")
		elif reason == "expiry":
			print("The stored tokens have expired.")
		else:
			print("Cannot access SplatNet 3 without having played online.")
			sys.exit(0)

	if SESSION_TOKEN == "":
		print("Please log in to your Nintendo Account to obtain your session_token.")
		new_token = iksm.log_in(A_VERSION, APP_USER_AGENT, F_GEN_URL)
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
		acc_lang = "en-US" # overwritten by user setting
		acc_country = "US"
		print("Using `US` for country by default. This can be changed in config.txt.")
	else:
		print("Attempting to generate new gtoken and bulletToken...")
		new_gtoken, acc_name, acc_lang, acc_country = iksm.get_gtoken(F_GEN_URL, SESSION_TOKEN, A_VERSION)
		new_bullettoken = iksm.get_bullet(new_gtoken, APP_USER_AGENT, acc_lang, acc_country)
	CONFIG_DATA["gtoken"] = new_gtoken # valid for 6 hours
	CONFIG_DATA["bullettoken"] = new_bullettoken # valid for 2 hours

	global USER_LANG
	if acc_lang != USER_LANG:
		acc_lang = USER_LANG
	CONFIG_DATA["acc_loc"] = f"{acc_lang}|{acc_country}"

	write_config(CONFIG_DATA)

	if new_bullettoken == "":
		print("Wrote gtoken to config.txt, but could not generate bulletToken.")
		print("Is SplatNet 3 undergoing maintenance?")
		sys.exit(1)
	if manual_entry:
		print("Wrote tokens to config.txt.\n") # and updates acc_country if necessary...
	else:
		print(f"Wrote tokens for {acc_name} to config.txt.\n")


def fetch_json(which, separate=False, exportall=False, specific=False, numbers_only=False, printout=False, skipprefetch=False):
	'''Returns results JSON from SplatNet 3, including a combined dictionary for battles + SR jobs if requested.'''

	swim = SquidProgress()

	if DEBUG:
		print(f"* fetch_json() called with which={which}, separate={separate}, " \
			f"exportall={exportall}, specific={specific}, numbers_only={numbers_only}")

	if exportall and not separate:
		print("* fetch_json() must be called with separate=True if using exportall.")
		sys.exit(1)

	if not skipprefetch:
		prefetch_checks(printout)
		if DEBUG:
			print("* prefetch_checks() succeeded")
	else:
		if DEBUG:
			print("* skipping prefetch_checks()")
	swim()

	ink_list, salmon_list = [], []
	parent_files = []

	queries = []
	if which in ("both", "ink"):
		if specific in (True, "regular"):
			queries.append("RegularBattleHistoriesQuery")
		if specific in (True, "anarchy"):
			queries.append("BankaraBattleHistoriesQuery")
		if specific in (True, "x"):
			queries.append("XBattleHistoriesQuery")
		if specific in (True, "challenge"):
			queries.append("EventBattleHistoriesQuery")
		if specific in (True, "private") and not utils.custom_key_exists("ignore_private", CONFIG_DATA):
			queries.append("PrivateBattleHistoriesQuery")
		if not specific: # False
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
			lang = 'en-US' if sha == "CoopHistoryQuery" else None
			sha = utils.translate_rid[sha]
			battle_ids, job_ids = [], []

			query1 = requests.post(iksm.GRAPHQL_URL,
				data=utils.gen_graphql_body(sha),
				headers=headbutt(forcelang=lang),
				cookies=dict(_gtoken=GTOKEN))
			query1_resp = json.loads(query1.text)
			swim()

			if not query1_resp.get("data"): # catch error
				print("\nSomething's wrong with one of the query hashes. Ensure s3s is up-to-date, and if this message persists, please open an issue on GitHub.")
				sys.exit(1)

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
			# ink battles - latest 50 x battles
			elif "xBattleHistories" in query1_resp["data"]:
				needs_sorted = True
				for battle_group in query1_resp["data"]["xBattleHistories"]["historyGroups"]["nodes"]:
					for battle in battle_group["historyDetails"]["nodes"]:
						battle_ids.append(battle["id"])
			# ink battles - latest 50 challenge battles
			elif "eventBattleHistories" in query1_resp["data"]:
				needs_sorted = True
				for battle_group in query1_resp["data"]["eventBattleHistories"]["historyGroups"]["nodes"]:
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
				ink_list.extend(thread_pool.map(fetch_detailed_result, [True]*len(battle_ids), battle_ids, [swim]*len(battle_ids)))

				salmon_list.extend(thread_pool.map(fetch_detailed_result, [False]*len(job_ids), job_ids, [swim]*len(job_ids)))

				if needs_sorted: # put regular/bankara/event/private in order, b/c exported in sequential chunks
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


def fetch_detailed_result(is_vs_history, history_id, swim):
	'''Helper function for fetch_json().'''

	sha = "VsHistoryDetailQuery" if is_vs_history else "CoopHistoryDetailQuery"
	varname = "vsResultId" if is_vs_history else "coopHistoryDetailId"
	lang = None if is_vs_history else 'en-US'

	query2 = requests.post(iksm.GRAPHQL_URL,
		data=utils.gen_graphql_body(utils.translate_rid[sha], varname, history_id),
		headers=headbutt(forcelang=lang),
		cookies=dict(_gtoken=GTOKEN))
	query2_resp = json.loads(query2.text)

	swim()
	return query2_resp


def populate_gear_abilities(player):
	'''Returns string representing all 12 ability slots for the player's gear, for use in set_scoreboard().'''

	h_main = utils.translate_gear_ability(player["headGear"]["primaryGearPower"]["image"]["url"])
	h_subs = []
	if len(player["headGear"]["additionalGearPowers"]) > 0:
		h_subs.append(utils.translate_gear_ability(player["headGear"]["additionalGearPowers"][0]["image"]["url"]))
	if len(player["headGear"]["additionalGearPowers"]) > 1:
		h_subs.append(utils.translate_gear_ability(player["headGear"]["additionalGearPowers"][1]["image"]["url"]))
	if len(player["headGear"]["additionalGearPowers"]) > 2:
		h_subs.append(utils.translate_gear_ability(player["headGear"]["additionalGearPowers"][2]["image"]["url"]))

	c_main = utils.translate_gear_ability(player["clothingGear"]["primaryGearPower"]["image"]["url"])
	c_subs = []
	if len(player["clothingGear"]["additionalGearPowers"]) > 0:
		c_subs.append(utils.translate_gear_ability(player["clothingGear"]["additionalGearPowers"][0]["image"]["url"]))
	if len(player["clothingGear"]["additionalGearPowers"]) > 1:
		c_subs.append(utils.translate_gear_ability(player["clothingGear"]["additionalGearPowers"][1]["image"]["url"]))
	if len(player["clothingGear"]["additionalGearPowers"]) > 2:
		c_subs.append(utils.translate_gear_ability(player["clothingGear"]["additionalGearPowers"][2]["image"]["url"]))

	s_main = utils.translate_gear_ability(player["shoesGear"]["primaryGearPower"]["image"]["url"])
	s_subs = []
	if len(player["shoesGear"]["additionalGearPowers"]) > 0:
		s_subs.append(utils.translate_gear_ability(player["shoesGear"]["additionalGearPowers"][0]["image"]["url"]))
	if len(player["shoesGear"]["additionalGearPowers"]) > 1:
		s_subs.append(utils.translate_gear_ability(player["shoesGear"]["additionalGearPowers"][1]["image"]["url"]))
	if len(player["shoesGear"]["additionalGearPowers"]) > 2:
		s_subs.append(utils.translate_gear_ability(player["shoesGear"]["additionalGearPowers"][2]["image"]["url"]))

	return h_main, h_subs, c_main, c_subs, s_main, s_subs


def set_scoreboard(battle, tricolor=False):
	'''Returns lists of player dictionaries: our_team_players, their_team_players, and optionally third_team_players.'''

	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Battle-%EF%BC%8D-Post#player-structure
	our_team_players, their_team_players, third_team_players = [], [], []

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
		p_dict["species"]         = player["species"].lower()
		p_dict["rank_in_team"]    = i+1

		if player.get("crown"):
			p_dict["crown_type"] = "x"
		if "DRAGON" in player.get("festDragonCert", ""):
			if player["festDragonCert"] == "DRAGON":
				p_dict["crown_type"] = "100x"
			elif player["festDragonCert"] == "DOUBLE_DRAGON":
				p_dict["crown_type"] = "333x"

		if "result" in player and player["result"] is not None:
			p_dict["kill_or_assist"] = player["result"]["kill"]
			p_dict["assist"]         = player["result"]["assist"]
			p_dict["kill"]           = p_dict["kill_or_assist"] - p_dict["assist"]
			p_dict["death"]          = player["result"]["death"]
			p_dict["special"]        = player["result"]["special"]
			p_dict["signal"]         = player["result"]["noroshiTry"]
			p_dict["disconnected"]   = "no"
			p_dict["crown"]          = "yes" if player.get("crown") == True else "no"

			# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Battle-%EF%BC%8D-Post#gears-structure
			gear_struct = {"headgear": {}, "clothing": {}, "shoes": {}}
			h_main, h_subs, c_main, c_subs, s_main, s_subs = populate_gear_abilities(player)
			gear_struct["headgear"] = {"primary_ability": h_main, "secondary_abilities": h_subs}
			gear_struct["clothing"] = {"primary_ability": c_main, "secondary_abilities": c_subs}
			gear_struct["shoes"]    = {"primary_ability": s_main, "secondary_abilities": s_subs}
			p_dict["gears"] = gear_struct
		else:
			p_dict["disconnected"]   = "yes"
		our_team_players.append(p_dict)

	team_nums = [0, 1] if tricolor else [0]
	for team_num in team_nums:
		for i, player in enumerate(battle["otherTeams"][team_num]["players"]):
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
			p_dict["species"]         = player["species"].lower()
			p_dict["rank_in_team"]    = i+1

			if player.get("crown"):
				p_dict["crown_type"] = "x"
			if "DRAGON" in player.get("festDragonCert", ""):
				if player["festDragonCert"] == "DRAGON":
					p_dict["crown_type"] = "100x"
				elif player["festDragonCert"] == "DOUBLE_DRAGON":
					p_dict["crown_type"] = "333x"

			if "result" in player and player["result"] is not None:
				p_dict["kill_or_assist"] = player["result"]["kill"]
				p_dict["assist"]         = player["result"]["assist"]
				p_dict["kill"]           = p_dict["kill_or_assist"] - p_dict["assist"]
				p_dict["death"]          = player["result"]["death"]
				p_dict["special"]        = player["result"]["special"]
				p_dict["signal"]         = player["result"]["noroshiTry"]
				p_dict["disconnected"]   = "no"
				p_dict["crown"]          = "yes" if player.get("crown") == True else "no"

				gear_struct = {"headgear": {}, "clothing": {}, "shoes": {}}
				h_main, h_subs, c_main, c_subs, s_main, s_subs = populate_gear_abilities(player)
				gear_struct["headgear"] = {"primary_ability": h_main, "secondary_abilities": h_subs}
				gear_struct["clothing"] = {"primary_ability": c_main, "secondary_abilities": c_subs}
				gear_struct["shoes"]    = {"primary_ability": s_main, "secondary_abilities": s_subs}
				p_dict["gears"] = gear_struct
			else:
				p_dict["disconnected"]   = "yes"
			if team_num == 0:
				their_team_players.append(p_dict)
			elif team_num == 1:
				third_team_players.append(p_dict)

	if tricolor:
		return our_team_players, their_team_players, third_team_players
	else:
		return our_team_players, their_team_players


def prepare_battle_result(battle, ismonitoring, isblackout, overview_data=None):
	'''Converts the Nintendo JSON format for a battle to the stat.ink one.'''

	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Battle-%EF%BC%8D-Post
	payload = {}
	battle = battle["vsHistoryDetail"]

	## UUID ##
	##########
	try:
		full_id = utils.b64d(battle["id"])
		payload["uuid"] = str(uuid.uuid5(utils.S3S_NAMESPACE, full_id[-52:])) # input format: <YYYYMMDD>T<HHMMSS>_<uuid>
	except TypeError:
		print("Couldn't get the battle ID. This is likely an error on Nintendo's end; running the script again may fix it. Exiting.")
		print('\nDebug info:')
		print(json.dumps(battle))
		sys.exit(1)

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
		if utils.b64d(battle["vsMode"]["id"]) in (6, 8): # open or tricolor
			payload["lobby"] = "splatfest_open"
		elif utils.b64d(battle["vsMode"]["id"]) == 7:
			payload["lobby"] = "splatfest_challenge" # pro
	elif mode == "X_MATCH":
		payload["lobby"] = "xmatch"
	elif mode == "LEAGUE": # challenge
		payload["lobby"] = "event"

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
	elif rule == "TRI_COLOR":
		payload["rule"] = "tricolor"

	## STAGE ##
	###########
	payload["stage"] = utils.b64d(battle["vsStage"]["id"])

	## WEAPON, K/D/A/S, PLAYER & TEAM TURF INKED ##
	###############################################
	for i, player in enumerate(battle["myTeam"]["players"]): # specified again in set_scoreboard()
		if player["isMyself"] == True:
			payload["weapon"]         = utils.b64d(player["weapon"]["id"])
			payload["inked"]          = player["paint"]
			payload["species"]        = player["species"].lower()
			payload["rank_in_team"]   = i+1
			# crowns (x rank and splatfest 'dragon') set in set_scoreboard()

			if player["result"] is not None: # null if player disconnect
				payload["kill_or_assist"] = player["result"]["kill"]
				payload["assist"]         = player["result"]["assist"]
				payload["kill"]           = payload["kill_or_assist"] - payload["assist"]
				payload["death"]          = player["result"]["death"]
				payload["special"]        = player["result"]["special"]
				payload["signal"]        = player["result"]["noroshiTry"] # ultra signal attempts in tricolor TW
				break

	try:
		our_team_inked, their_team_inked = 0, 0
		for player in battle["myTeam"]["players"]:
			our_team_inked += player["paint"]
		for player in battle["otherTeams"][0]["players"]:
			their_team_inked += player["paint"]
		payload["our_team_inked"] = our_team_inked
		payload["their_team_inked"] = their_team_inked
	except: # one of these might be able to be null? doubtful but idk lol
		pass

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

	## BASIC INFO & TURF WAR ##
	###########################
	if rule == "TURF_WAR" or rule == "TRI_COLOR": # could be turf war
		try:
			payload["our_team_percent"]   = float(battle["myTeam"]["result"]["paintRatio"]) * 100
			payload["their_team_percent"] = float(battle["otherTeams"][0]["result"]["paintRatio"]) * 100
		except: # draw - 'result' is null
			pass
	else: # could be a ranked mode
		try:
			payload["knockout"] = "no" if battle["knockout"] is None or battle["knockout"] == "NEITHER" else "yes"
			payload["our_team_count"]   = battle["myTeam"]["result"]["score"]
			payload["their_team_count"] = battle["otherTeams"][0]["result"]["score"]
		except: # draw - 'result' is null
			pass

	## START/END TIMES ##
	#####################
	payload["start_at"] = utils.epoch_time(battle["playedTime"])
	payload["end_at"]   = payload["start_at"] + battle["duration"]

	## SCOREBOARD & COLOR ##
	########################
	payload["our_team_color"]   = utils.convert_color(battle["myTeam"]["color"])
	payload["their_team_color"] = utils.convert_color(battle["otherTeams"][0]["color"])

	if rule != "TRI_COLOR":
		payload["our_team_players"], payload["their_team_players"] = set_scoreboard(battle)
	else:
		payload["our_team_players"], payload["their_team_players"], payload["third_team_players"] = set_scoreboard(battle, tricolor=True)
		payload["third_team_color"] = utils.convert_color(battle["otherTeams"][1]["color"])

	## SPLATFEST ##
	###############
	if mode == "FEST":
		# paint %ages set in 'basic info'
		payload["our_team_theme"]   = battle["myTeam"]["festTeamName"]
		payload["their_team_theme"] = battle["otherTeams"][0]["festTeamName"]

		# NORMAL (1x), DECUPLE (10x), DRAGON (100x), DOUBLE_DRAGON (333x)
		times_battle = battle["festMatch"]["dragonMatchType"]
		if times_battle == "DECUPLE":
			payload["fest_dragon"] = "10x"
		elif times_battle == "DRAGON":
			payload["fest_dragon"] = "100x"
		elif times_battle == "DOUBLE_DRAGON":
			payload["fest_dragon"] = "333x"
		elif times_battle == "CONCH_SHELL_SCRAMBLE":
			payload["conch_clash"] = "1x"
		elif times_battle == "CONCH_SHELL_SCRAMBLE_10":
			payload["conch_clash"] = "10x"
		elif times_battle == "CONCH_SHELL_SCRAMBLE_33": # presumed
			payload["conch_clash"] = "33x"

		payload["clout_change"] = battle["festMatch"]["contribution"]
		payload["fest_power"]   = battle["festMatch"]["myFestPower"] # pro only

	## TRICOLOR TW ##
	#################
	if mode == "FEST" and rule == "TRI_COLOR":
		try:
			payload["third_team_percent"] = float(battle["otherTeams"][1]["result"]["paintRatio"]) * 100
		except TypeError:
			pass

		third_team_inked = 0
		for player in battle["otherTeams"][1]["players"]:
			third_team_inked += player["paint"]
		payload["third_team_inked"] = third_team_inked

		payload["third_team_theme"] = battle["otherTeams"][1]["festTeamName"]

		payload["our_team_role"]   = utils.convert_tricolor_role(battle["myTeam"]["tricolorRole"])
		payload["their_team_role"] = utils.convert_tricolor_role(battle["otherTeams"][0]["tricolorRole"])
		payload["third_team_role"] = utils.convert_tricolor_role(battle["otherTeams"][1]["tricolorRole"])

	## ANARCHY BATTLES ##
	#####################
	if mode == "BANKARA":
		# counts & knockout set in 'basic info'
		payload["rank_exp_change"] = battle["bankaraMatch"]["earnedUdemaePoint"]

		try: # if playing in anarchy open with 2-4 people, after 5 calibration matches
			payload["bankara_power_after"] = battle["bankaraMatch"]["bankaraPower"]["power"]
		except: # could be null in historical data
			pass

		battle_id         = base64.b64decode(battle["id"]).decode('utf-8')
		battle_id_mutated = battle_id.replace("BANKARA", "RECENT") # normalize the ID, make work with -M and -r

		if overview_data is None: # no passed in file with -i
			overview_post = requests.post(iksm.GRAPHQL_URL,
				data=utils.gen_graphql_body(utils.translate_rid["BankaraBattleHistoriesQuery"]),
				headers=headbutt(),
				cookies=dict(_gtoken=GTOKEN))
			try:
				overview_data = [json.loads(overview_post.text)] # make the request in real-time in attempt to get rank, etc.
			except:
				overview_data = None
				print("Failed to get recent Anarchy Battles. Proceeding without information on current rank.")
		if overview_data is not None:
			ranked_list = []
			for screen in overview_data:
				if "bankaraBattleHistories" in screen["data"]:
					ranked_list = screen["data"]["bankaraBattleHistories"]["historyGroups"]["nodes"]
					break
				elif "latestBattleHistories" in screen["data"]: # early exports used this, and no bankaraMatchChallenge below
					ranked_list = screen["data"]["latestBattleHistories"]["historyGroups"]["nodes"]
					break
			for parent in ranked_list: # groups in overview (anarchy tab) JSON/screen
				for idx, child in enumerate(parent["historyDetails"]["nodes"]):

					# same battle, different screens
					overview_battle_id         = base64.b64decode(child["id"]).decode('utf-8')
					overview_battle_id_mutated = overview_battle_id.replace("BANKARA", "RECENT")

					if overview_battle_id_mutated == battle_id_mutated: # found the battle ID in the other file
						full_rank = re.split('([0-9]+)', child["udemae"].lower())
						was_s_plus_before = len(full_rank) > 1 # true if "before" rank is s+

						payload["rank_before"] = full_rank[0]
						if was_s_plus_before:
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

							if parent["bankaraMatchChallenge"]["udemaeAfter"] is not None:
								if idx != 0:
									payload["rank_after"] = payload["rank_before"]
									if was_s_plus_before: # not a rank-up battle, so must be the same
										payload["rank_after_s_plus"] = payload["rank_before_s_plus"]
								else: # the battle where we actually ranked up
									full_rank_after = re.split('([0-9]+)', parent["bankaraMatchChallenge"]["udemaeAfter"].lower())
									payload["rank_after"] = full_rank_after[0]
									if len(full_rank_after) > 1:
										payload["rank_after_s_plus"] = int(full_rank_after[1])

							if idx == 0: # for the most recent battle in the series only
								# send overall win/lose count
								payload["challenge_win"] = parent["bankaraMatchChallenge"]["winCount"]
								payload["challenge_lose"] = parent["bankaraMatchChallenge"]["loseCount"]

								# send exp change (gain)
								if payload["rank_exp_change"] is None:
									payload["rank_exp_change"] = parent["bankaraMatchChallenge"]["earnedUdemaePoint"]

							if DEBUG:
								print(f'* {battle["judgement"]} {idx}')
								print(f'* rank_before: {payload["rank_before"]}')
								print(f'* rank_after: {payload["rank_after"]}')
								print(f'* rank up battle: {parent["bankaraMatchChallenge"]["isPromo"]}')
								print(f'* is ranked up: {parent["bankaraMatchChallenge"]["isUdemaeUp"]}')
								if idx == 0:
									print(f'* rank_exp_change: {parent["bankaraMatchChallenge"]["earnedUdemaePoint"]}')
								else:
									print(f'* rank_exp_change: 0')
						break # found the child ID, no need to continue

	## X BATTLES ##
	###############
	if mode == "X_MATCH":
		# counts & knockout set in 'basic info'
		if battle["xMatch"]["lastXPower"] is not None:
			payload["x_power_before"] = battle["xMatch"]["lastXPower"]

		battle_id         = base64.b64decode(battle["id"]).decode('utf-8')
		battle_id_mutated = battle_id.replace("XMATCH", "RECENT")

		if overview_data is None: # no passed in file with -i
			overview_post = requests.post(iksm.GRAPHQL_URL,
				data=utils.gen_graphql_body(utils.translate_rid["XBattleHistoriesQuery"]),
				headers=headbutt(),
				cookies=dict(_gtoken=GTOKEN))
			try:
				overview_data = [json.loads(overview_post.text)] # make the request in real-time in attempt to get rank, etc.
			except:
				overview_data = None
				print("Failed to get recent X Battles. Proceeding without some information on X Power.")
		if overview_data is not None:
			x_list = []
			for screen in overview_data:
				if "xBattleHistories" in screen["data"]:
					x_list = screen["data"]["xBattleHistories"]["historyGroups"]["nodes"]
					break
			for parent in x_list: # groups in overview (x tab) JSON/screen
				for idx, child in enumerate(parent["historyDetails"]["nodes"]):

					overview_battle_id         = base64.b64decode(child["id"]).decode('utf-8')
					overview_battle_id_mutated = overview_battle_id.replace("XMATCH", "RECENT")

					if overview_battle_id_mutated == battle_id_mutated:
						if idx == 0:
							# best of 5 for getting x power at season start, best of 3 after
							payload["challenge_win"] = parent["xMatchMeasurement"]["winCount"]
							payload["challenge_lose"] = parent["xMatchMeasurement"]["loseCount"]

							if parent["xMatchMeasurement"]["state"] == "COMPLETED":
								payload["x_power_after"] = parent["xMatchMeasurement"]["xPowerAfter"]
							break

	## CHALLENGES ##
	################
	if mode == "LEAGUE":
		payload["event"] = battle["leagueMatch"]["leagueMatchEvent"]["id"] # send in Base64
		payload["event_power"] = battle["leagueMatch"]["myLeaguePower"]
		# luckily no need to look at overview screen for any info

		# to check: any ranked-specific stuff for challenges in battle.leagueMatch...?

	## MEDALS ##
	############
	medals = []
	for medal in battle["awards"]:
		medals.append(medal["name"])
	payload["medals"] = medals

	# no way to get: level_before/after, cash_before/after

	payload["automated"] = "yes" # data was not manually entered!

	if isblackout:
		# fix payload
		for player in payload["our_team_players"]:
			if player["me"] == "no": # only black out others
				player["name"] = None
				player["number"] = None
				player["splashtag_title"] = None
		for player in payload["their_team_players"]:
			player["name"] = None
			player["number"] = None
			player["splashtag_title"] = None
		if "third_team_players" in payload:
			for player in payload["third_team_players"]:
				player["name"] = None
				player["number"] = None
				player["splashtag_title"] = None

		# fix battle json
		for player in battle["myTeam"]["players"]:
			if not player["isMyself"]: # only black out others
				player["name"] = None
				player["nameId"] = None
				player["byname"] = None
		for team in battle["otherTeams"]:
			for player in team["players"]:
				player["name"] = None
				player["nameId"] = None
				player["byname"] = None

	payload["splatnet_json"] = json.dumps(battle)

	return payload


def prepare_job_result(job, ismonitoring, isblackout, overview_data=None, prevresult=None):
	'''Converts the Nintendo JSON format for a Salmon Run job to the stat.ink one.'''

	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Salmon-%EF%BC%8D-Post
	payload = {}
	job = job["coopHistoryDetail"]

	full_id = utils.b64d(job["id"])
	payload["uuid"] = str(uuid.uuid5(utils.SALMON_NAMESPACE, full_id))

	job_rule = job["rule"]
	if job_rule in ("PRIVATE_CUSTOM", "PRIVATE_SCENARIO"):
		payload["private"] = "yes"
	else:
		payload["private"] = "yes" if job["jobPoint"] is None else "no"
	is_private = True if payload["private"] == "yes" else False

	payload["big_run"]      = "yes" if job_rule == "BIG_RUN"      else "no"
	payload["eggstra_work"] = "yes" if job_rule == "TEAM_CONTEST" else "no"

	payload["stage"] = utils.b64d(job["coopStage"]["id"])

	if job_rule != "TEAM_CONTEST": # not present for overall job in eggstra work
		payload["danger_rate"] = job["dangerRate"] * 100
	payload["king_smell"] = job["smellMeter"]

	waves_cleared = job["resultWave"] - 1 # resultWave = 0 if all normal waves cleared
	max_waves = 5 if job_rule == "TEAM_CONTEST" else 3
	payload["clear_waves"] = max_waves if waves_cleared == -1 else waves_cleared

	if payload["clear_waves"] < 0: # player dc'd
		payload["clear_waves"] = None

	elif payload["clear_waves"] != max_waves: # job failure
		last_wave = job["waveResults"][payload["clear_waves"]]
		if last_wave["teamDeliverCount"] >= last_wave["deliverNorm"]: # delivered more than quota, but still failed
			payload["fail_reason"] = "wipe_out"

	# xtrawave only
	# https://stat.ink/api-info/boss-salmonid3
	if job["bossResult"]:
		try:
			payload["king_salmonid"] = utils.b64d(job["bossResult"]["boss"]["id"])
		except KeyError:
			print("Could not send unsupported King Salmonid data to stat.ink. You may want to delete & re-upload this job later.")

		payload["clear_extra"] = "yes" if job["bossResult"]["hasDefeatBoss"] else "no"

	# https://stat.ink/api-info/salmon-title3
	if not is_private and job_rule != "TEAM_CONTEST": # only in regular, not private or eggstra work
		payload["title_after"]     = utils.b64d(job["afterGrade"]["id"])
		payload["title_exp_after"] = job["afterGradePoint"]

		# never sure of points gained unless first job of rot - wave 3 clear is usu. +20, but 0 if playing w/ diff-titled friends
		if job.get("previousHistoryDetail") != None:
			prev_job_id = job["previousHistoryDetail"]["id"]

			if overview_data: # passed in a file, so no web request needed
				if prevresult:
					# compare stage - if different, this is the first job of a rotation, where you start at 40
					if job["coopStage"]["id"] != prevresult["coopHistoryDetail"]["coopStage"]["id"]:
						payload["title_before"]     = payload["title_after"] # can't go up or down from just one job
						payload["title_exp_before"] = 40
					else:
						try:
							payload["title_before"]     = utils.b64d(prevresult["coopHistoryDetail"]["afterGrade"]["id"])
							payload["title_exp_before"] = prevresult["coopHistoryDetail"]["afterGradePoint"]
						except KeyError: # prev job was private or disconnect
							pass
			else:
				prev_job_post = requests.post(iksm.GRAPHQL_URL,
					data=utils.gen_graphql_body(utils.translate_rid["CoopHistoryDetailQuery"], "coopHistoryDetailId", prev_job_id),
					headers=headbutt(forcelang='en-US'),
					cookies=dict(_gtoken=GTOKEN))
				try:
					prev_job = json.loads(prev_job_post.text)

					# do stage comparison again
					if job["coopStage"]["id"] != prev_job["data"]["coopHistoryDetail"]["coopStage"]["id"]:
						payload["title_before"]     = payload["title_after"]
						payload["title_exp_before"] = 40
					else:
						try:
							payload["title_before"] = utils.b64d(prev_job["data"]["coopHistoryDetail"]["afterGrade"]["id"])
							payload["title_exp_before"] = prev_job["data"]["coopHistoryDetail"]["afterGradePoint"]
						except (KeyError, TypeError): # private or disconnect, or the json was invalid (expired job >50 ago) or something
							pass
				except json.decoder.JSONDecodeError:
					pass

	geggs = 0
	peggs = job["myResult"]["deliverCount"]
	for player in job["memberResults"]:
		peggs += player["deliverCount"]
	for wave in job["waveResults"]:
		geggs += wave["teamDeliverCount"] if wave["teamDeliverCount"] != None else 0
	payload["golden_eggs"] = geggs
	payload["power_eggs"]  = peggs

	if job["scale"]:
		payload["gold_scale"]   = job["scale"]["gold"]
		payload["silver_scale"] = job["scale"]["silver"]
		payload["bronze_scale"] = job["scale"]["bronze"]

	payload["job_score"] = job["jobScore"] # job score
	payload["job_rate"]  = job["jobRate"]  # pay grade
	payload["job_bonus"] = job["jobBonus"] # clear bonus
	payload["job_point"] = job["jobPoint"] # your points = floor((score x rate) + bonus)
	# note the current bug with "bonus" lol... https://github.com/frozenpandaman/s3s/wiki/%7C-splatnet-bugs

	# species sent in player struct

	translate_special = { # used in players and waves below
		20006: "nicedama",
		20007: "hopsonar",
		20009: "megaphone51",
		20010: "jetpack",
		20012: "kanitank",
		20013: "sameride",
		20014: "tripletornado",
		20017: "teioika",
		20018: "ultra_chakuchi"
	}

	players = []
	players_json = [job["myResult"]]
	for teammate in job["memberResults"]:
		players_json.append(teammate)

	for i, player in enumerate(players_json):
		player_info = {}
		player_info["me"]              = "yes" if i == 0 else "no"
		player_info["name"]            = player["player"]["name"]
		player_info["number"]          = player["player"]["nameId"]
		player_info["splashtag_title"] = player["player"]["byname"]
		player_info["golden_eggs"]     = player["goldenDeliverCount"]
		player_info["golden_assist"]   = player["goldenAssistCount"]
		player_info["power_eggs"]      = player["deliverCount"]
		player_info["rescue"]          = player["rescueCount"]
		player_info["rescued"]         = player["rescuedCount"]
		player_info["defeat_boss"]     = player["defeatEnemyCount"]
		player_info["species"]         = player["player"]["species"].lower()

		dc_indicators = [
			player_info["golden_eggs"],
			player_info["power_eggs"],
			player_info["rescue"],
			player_info["rescued"],
			player_info["defeat_boss"]
		]
		player_info["disconnected"] = "yes" if all(value == 0 for value in dc_indicators) else "no"

		try:
			player_info["uniform"] = utils.b64d(player["player"]["uniform"]["id"])
		except KeyError:
			print("Could not send unsupported Salmon Run gear data to stat.ink. You may want to delete & re-upload this job later.")

		if player["specialWeapon"]: # if null, player dc'd
			try:
				special_id = player["specialWeapon"]["weaponId"] # post-v2.0.0 key
			except KeyError:
				special_id = utils.b64d(player["specialWeapon"]["id"])
			try:
				player_info["special"] = translate_special[special_id]
			except KeyError: # invalid special weapon - likely defaulted to '1' before it could be assigned
				pass

		weapons = []
		gave_warning = False
		for weapon in player["weapons"]: # should always be returned in in english due to headbutt() using forcelang
			wep_string = weapon["name"].lower().replace(" ", "_").replace("-", "_").replace(".", "").replace("'", "")
			if wep_string == "random": # NINTENDOOOOOOO
				wep_string = None
			else:
				try:
					wep_string.encode(encoding='utf-8').decode('ascii')
				except UnicodeDecodeError: # detect non-latin characters... not all non-english strings, but many
					wep_string = None
					if not gave_warning:
						gave_warning = True
						print("(!) Proceeding without weapon names. See https://github.com/frozenpandaman/s3s/issues/95 to fix this.")

			weapons.append(wep_string)
		player_info["weapons"] = weapons

		players.append(player_info)
	payload["players"] = players

	waves = []
	for i, wave in enumerate(job["waveResults"]):
		wave_info = {}
		wave_info["tide"]               = "low" if wave["waterLevel"] == 0 else "high" if wave["waterLevel"] == 2 else "normal"
		wave_info["golden_quota"]       = wave["deliverNorm"]
		wave_info["golden_delivered"]   = wave["teamDeliverCount"]
		wave_info["golden_appearances"] = wave["goldenPopCount"]
		if job_rule == "TEAM_CONTEST": # waves only have indiv hazard levels in eggstra work
			if i == 0:
				haz_level = 60
			else:
				num_players = len(players)
				quota         = waves[-1]["golden_quota"] # last wave, most recent one added to the list
				delivered     = waves[-1]["golden_delivered"]
				added_percent = 0 # default, no increase if less than 1.5x quota delivered
				if num_players == 4:
					if delivered >= quota*2:
						added_percent = 60
					elif delivered >= quota*1.5:
						added_percent = 30
				elif num_players == 3:
					if delivered >= quota*2:
						added_percent = 40
					elif delivered >= quota*1.5:
						added_percent = 20
				elif num_players == 2:
					if delivered >= quota*2:
						added_percent = 20
					elif delivered >= quota*1.5:
						added_percent = 10
				elif num_players == 1:
					if delivered >= quota*2:
						added_percent = 10
					elif delivered >= quota*1.5:
						added_percent = 5

				prev_percent = waves[-1]["danger_rate"]

				haz_level = prev_percent + added_percent
			wave_info["danger_rate"] = haz_level

		if wave["eventWave"]:
			event_id = utils.b64d(wave["eventWave"]["id"])
			translate_occurrence = {
				1: "rush",
				2: "goldie_seeking",
				3: "the_griller",
				4: "the_mothership",
				5: "fog",
				6: "cohock_charge",
				7: "giant_tornado",
				8: "mudmouth_eruption"
			}
			wave_info["event"] = translate_occurrence[event_id]

		special_uses = {
			"nicedama": 0,
			"hopsonar": 0,
			"megaphone51": 0,
			"jetpack": 0,
			"kanitank": 0,
			"sameride": 0,
			"tripletornado": 0,
			"teioika": 0,
			"ultra_chakuchi": 0,
			"unknown": 0
		}
		for wep_use in wave["specialWeapons"]:
			special_id = utils.b64d(wep_use["id"])
			special_key = translate_special.get(special_id, "unknown")
			special_uses[special_key] += 1 # increment value of the key each time it's found
		wave_info["special_uses"] = special_uses

		waves.append(wave_info)
	payload["waves"] = waves

	# https://stat.ink/api-info/boss-salmonid3
	bosses = {}
	translate_boss = {
		4:  "bakudan",
		5:  "katapad",
		6:  "teppan",
		7:  "hebi",
		8:  "tower",
		9:  "mogura",
		10: "koumori",
		11: "hashira",
		12: "diver",
		13: "tekkyu",
		14: "nabebuta",
		15: "kin_shake",
		17: "grill",
		20: "doro_shake"
	}
	for boss in job["enemyResults"]:
		boss_id  = utils.b64d(boss["enemy"]["id"])
		boss_key = translate_boss[boss_id]
		bosses[boss_key] = {
			"appearances":    boss["popCount"],
			"defeated":       boss["teamDefeatCount"],
			"defeated_by_me": boss["defeatCount"]
		}
	payload["bosses"] = bosses

	payload["start_at"] = utils.epoch_time(job["playedTime"])

	if isblackout:
		# fix payload
		for player in payload["players"]:
			if player["me"] == "no":
				player["name"] = None
				player["number"] = None
				player["splashtag_title"] = None

		# fix job json
		for player in job["memberResults"]:
			player["player"]["name"] = None
			player["player"]["nameId"] = None
			player["player"]["byname"] = None

	payload["splatnet_json"] = json.dumps(job)
	payload["automated"] = "yes"

	return payload


def post_result(data, ismonitoring, isblackout, istestrun, overview_data=None):
	'''Uploads battle/job JSON to stat.ink, and prints the returned URL or error message.'''

	if len(API_KEY) != 43:
		print("Cannot post to stat.ink without a valid API key set in config.txt. Exiting.")
		sys.exit(0)

	if isinstance(data, list): # -o export format
		try:
			data = [x for x in data if x["data"]["vsHistoryDetail"] is not None] # avoid {"data": {"vsHistoryDetail": None}} error
			results = sorted(data, key=lambda d: d["data"]["vsHistoryDetail"]["playedTime"])
		except KeyError:
			try:
				data = [x for x in data if x["data"]["coopHistoryDetail"] is not None]
				results = sorted(data, key=lambda d: d["data"]["coopHistoryDetail"]["playedTime"])
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
			payload = prepare_battle_result(results[i]["data"], ismonitoring, isblackout, overview_data)
			which = "ink"
		elif "coopHistoryDetail" in results[i]["data"]: # salmon run job
			prevresult = results[i-1]["data"] if i > 0 else None
			payload = prepare_job_result(results[i]["data"], ismonitoring, isblackout, overview_data, prevresult=prevresult)
			which = "salmon"
		else: # shouldn't happen
			print("Ill-formatted JSON while uploading. Exiting.")
			print('\nDebug info:')
			print(json.dumps(results))
			sys.exit(1) # always exit here - something is seriously wrong

		if not payload: # empty payload
			return

		if len(payload) == 0: # received blank payload from prepare_job_result() - skip unsupported battle
			continue

		# should have been taken care of in fetch_json() but just in case...
		if payload.get("lobby") == "private" and utils.custom_key_exists("ignore_private", CONFIG_DATA) or \
			payload.get("private") == "yes" and utils.custom_key_exists("ignore_private_jobs", CONFIG_DATA): # SR version
			continue

		s3s_values = {'agent': '\u0073\u0033\u0073', 'agent_version': f'v{A_VERSION}'} # lol
		s3s_values["agent_variables"] = {'Upload Mode': "Monitoring" if ismonitoring else "Manual"}
		payload.update(s3s_values)

		if payload["agent"][0:3] != os.path.basename(__file__)[:-3]:
			print("Could not upload. Please contact @frozenpandaman on GitHub for assistance.")
			sys.exit(0)

		if istestrun:
			payload["test"] = "yes"

		# POST
		url = "https://stat.ink/api/v3"
		if which == "ink":
			url += "/battle"
		elif which == "salmon":
			url += "/salmon"
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

		detail_type = "vsHistoryDetail" if which == "ink" else "coopHistoryDetail"
		result_id = results[i]["data"][detail_type]["id"]
		noun = utils.set_noun(which)[:-1]

		if DEBUG:
			print(f"* time uploaded: {time_uploaded}; time now: {time_now}")

		if istestrun and postbattle.status_code == 200:
			print(f"Successfully validated {noun} ID {result_id} with stat.ink.")

		elif postbattle.status_code != 201: # Created (or already exists)
			print(f"Error uploading {noun}. (ID: {result_id})")
			print("Message from server:")
			print(postbattle.content.decode('utf-8'))

		elif time_uploaded <= time_now - 7: # give some leeway
			print(f"{noun.capitalize()} already uploaded - {headerloc}")

		else: # 200 OK
			print(f"{noun.capitalize()} uploaded to {headerloc}")


def check_for_updates():
	'''Checks the script version against the repo, reminding users to update if available.'''

	try:
		latest_script = requests.get("https://raw.githubusercontent.com/frozenpandaman/s3s/master/s3s.py")
		new_version = re.search(r'A_VERSION = "([\d.]*)"', latest_script.text).group(1)
		update_available = version.parse(new_version) > version.parse(A_VERSION)
		if update_available:
			print(f"\nThere is a new version (v{new_version}) available.", end='')
			if os.path.isdir(".git"):
				update_now = input("\nWould you like to update now? [Y/n] ")
				if update_now == "" or update_now[0].lower() == "y":
					FNULL = open(os.devnull, "w")
					call(["git", "checkout", "."], stdout=FNULL, stderr=FNULL)
					call(["git", "checkout", "master"], stdout=FNULL, stderr=FNULL)
					call(["git", "pull"], stdout=FNULL, stderr=FNULL)
					print(f"Successfully updated to v{new_version}. Please restart s3s.")
					sys.exit(0)
				else:
					print("Please update to the latest version by running " \
						'`\033[91m' + "git pull" + '\033[0m' \
						"` as soon as possible.\n")
			else: # no git directory
				print(" Visit the site below to update:\nhttps://github.com/frozenpandaman/s3s\n")
	except Exception as e: # if there's a problem connecting to github
		print('\033[3m' + "» Couldn't connect to GitHub. Please update the script manually via " \
			'`\033[91m' + "git pull" + '\033[0m' + "`." + '\033[0m' + "\n")
		# print('\033[3m' + "» While s3s is in beta, please update the script regularly via " \
		# 	'`\033[91m' + "git pull" + '\033[0m' + "`." + '\033[0m' + "\n")


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


def set_language():
	'''Prompts the user to set their game language.'''

	if USER_LANG == "":
		print("Default locale is en-US. Press Enter to accept, or enter your own (see readme for list).")
		language_code = input("")

		if language_code == "":
			CONFIG_DATA["acc_loc"] = "en-US|US" # default
			write_config(CONFIG_DATA)
			return
		else:
			language_list = [
				"de-DE", "en-GB", "en-US", "es-ES", "es-MX", "fr-CA", "fr-FR",
				"it-IT", "ja-JP", "ko-KR", "nl-NL", "ru-RU", "zh-CN", "zh-TW"
			]
			while language_code not in language_list:
				print("Invalid language code. Please try entering it again:")
				language_code = input("")
			CONFIG_DATA["acc_loc"] = f"{language_code}|US" # default to US until set by ninty
			write_config(CONFIG_DATA)
	return


def get_num_results(which):
	'''I/O for getting number of battles/jobs to upload.'''

	noun = utils.set_noun(which)
	try:
		if which == "ink":
			print(f"Note: This is an atypical way to run the script for manually specifying the number of recent " \
				"battles to upload, with a maximum of 50. Up to 250 recent battles (50 of each type) can be " \
				"uploaded automatically by appending the " + '\033[91m' + "-r" + '\033[0m' + " flag.\n")
		elif which == "salmon":
			print(f"Note: This is an atypical way to run the script for manually specifying the number of recent " \
				"Salmon Run jobs to upload. All 50 recent jobs can be uploaded automatically by appending the " \
				'\033[91m' + "-r" + '\033[0m' + " flag.\n")
		n = int(input(f"Number of recent {noun} to upload (0-50)? "))
		print()
	except ValueError:
		print("Please enter an integer between 0 and 50. Exiting.")
		sys.exit(0)
	if n == 0:
		print("Exiting without uploading anything.")
		sys.exit(0)
	elif n < 0:
		print("No.")
		sys.exit(0)
	elif n > 50:
		if which == "salmon":
			print("SplatNet 3 only stores the 50 most recent jobs. Exiting.")
		elif which == "ink":
			print("In this mode, s3s can only fetch the 50 most recent battles (of any type) at once. " \
				"Run the script with " \
				'\033[91m' + "-r" + '\033[0m' + " to fetch more than 50 results. Exiting.")
		sys.exit(0)
	else:
		return n


def fetch_and_upload_single_result(hash_, noun, isblackout, istestrun):
	'''Performs a GraphQL request for a single vsResultId/coopHistoryDetailId and call post_result().'''

	if noun in ("battles", "battle"):
		dict_key  = "VsHistoryDetailQuery"
		dict_key2 = "vsResultId"
		lang = None
	else: # noun == "jobs" or "job"
		dict_key  = "CoopHistoryDetailQuery"
		dict_key2 = "coopHistoryDetailId"
		lang = 'en-US'

	result_post = requests.post(iksm.GRAPHQL_URL,
			data=utils.gen_graphql_body(utils.translate_rid[dict_key], dict_key2, hash_),
			headers=headbutt(forcelang=lang),
			cookies=dict(_gtoken=GTOKEN))
	try:
		result = json.loads(result_post.text)
		post_result(result, False, isblackout, istestrun) # not monitoring mode
	except json.decoder.JSONDecodeError: # retry once, hopefully avoid a few errors
		result_post = requests.post(iksm.GRAPHQL_URL,
				data=utils.gen_graphql_body(utils.translate_rid[dict_key], dict_key2, hash_),
				headers=headbutt(forcelang=lang),
				cookies=dict(_gtoken=GTOKEN))
		try:
			result = json.loads(result_post.text)
			post_result(result, False, isblackout, istestrun)
		except json.decoder.JSONDecodeError:
			if utils.custom_key_exists("errors_pass_silently", CONFIG_DATA):
				print("Error uploading one of your battles. Continuing...")
				pass
			else:
				print(f"(!) Error uploading one of your battles. Please try running s3s again. This may also be an error on Nintendo's end. See https://github.com/frozenpandaman/s3s/issues/189 for more info. Use the `errors_pass_silently` config key to skip this {noun} and continue running the script.")
				sys.exit(1)


def check_if_missing(which, isblackout, istestrun, skipprefetch):
	'''Checks for unuploaded battles and uploads any that are found (-r flag).'''

	noun = utils.set_noun(which)
	print(f"Checking if there are previously-unuploaded {noun}...")

	urls = []
	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Battle-%EF%BC%8D-Get-UUID-List-(for-s3s)
	# https://github.com/fetus-hina/stat.ink/wiki/Spl3-API:-Salmon-%EF%BC%8D-Get-UUID-List
	if which in ("both", "ink"):
		urls.append("https://stat.ink/api/v3/s3s/uuid-list?lobby=adaptive") # max 250 entries
	else:
		urls.append(None)
	if which in ("both", "salmon"):
		urls.append("https://stat.ink/api/v3/salmon/uuid-list")
	else:
		urls.append(None)

	noun = "battles" # first (and maybe only)
	which = "ink"
	for url in urls:
		if url is not None:
			printed = False
			auth = {'Authorization': f'Bearer {API_KEY}'}
			resp = requests.get(url, headers=auth)
			try:
				statink_uploads = json.loads(resp.text)
			except:
				if utils.custom_key_exists("errors_pass_silently", CONFIG_DATA):
					print(f"Error while checking recently-uploaded {noun}. Continuing...")
				else:
					print(f"Error while checking recently-uploaded {noun}. Is stat.ink down?")
					sys.exit(1)

			# ! fetch from online
			# specific - check ALL possible battles; printout - to show tokens are being checked at program start
			splatnet_ids = fetch_json(which, specific=True, numbers_only=True, printout=True, skipprefetch=skipprefetch)

			# same as code in -i section below...
			for id in reversed(splatnet_ids):
				full_id = utils.b64d(id)

				if which == "ink":
					old_battle_uuid = full_id[-36:]
					new_battle_uuid = str(uuid.uuid5(utils.S3S_NAMESPACE, full_id[-52:]))

					if new_battle_uuid in statink_uploads:
						continue
					if old_battle_uuid in statink_uploads:
						if not utils.custom_key_exists("force_uploads", CONFIG_DATA):
							continue

				elif which == "salmon":
					old_job_uuid = str(uuid.uuid5(utils.SALMON_NAMESPACE, full_id[-52:])) # used to do it incorrectly
					new_job_uuid = str(uuid.uuid5(utils.SALMON_NAMESPACE, full_id))
					if new_job_uuid in statink_uploads:
						continue
					if old_job_uuid in statink_uploads: # extremely low chance of conflicts... but force upload if so
						if not utils.custom_key_exists("force_uploads", CONFIG_DATA):
							continue

				if not printed:
					printed = True
					print(f"Previously-unuploaded {noun} detected. Uploading now...")

				fetch_and_upload_single_result(id, noun, isblackout, istestrun)

			if not printed:
				print(f"No previously-unuploaded {noun} found.")

		noun = "jobs" # for second run through the loop
		which = "salmon"


def check_for_new_results(which, cached_battles, cached_jobs, battle_wins, battle_losses, battle_draws, splatfest_wins, splatfest_losses, splatfest_draws, mirror_matches, job_successes, job_failures, isblackout, istestrun):
	'''Helper function for monitor_battles(), called every N seconds or when exiting.'''

	# ! fetch from online
	# check only numbers (quicker); specific=False since checks recent (latest) only
	try:
		ink_results, salmon_results = fetch_json(which, separate=True, numbers_only=True)
	except: # e.g. JSONDecodeError - tokens have probably expired
		gen_new_tokens("expiry") # we don't have to do prefetch_checks(), we know they're expired. gen new ones and try again
		ink_results, salmon_results = fetch_json(which, separate=True, numbers_only=True)
	foundany = False

	if which in ("both", "ink"):
		for num in reversed(ink_results):
			if num not in cached_battles:
				# get the full battle data
				result_post = requests.post(iksm.GRAPHQL_URL,
					data=utils.gen_graphql_body(utils.translate_rid["VsHistoryDetailQuery"], "vsResultId", num),
					headers=headbutt(),
					cookies=dict(_gtoken=GTOKEN))
				result = json.loads(result_post.text)

				if result["data"]["vsHistoryDetail"]["vsMode"]["mode"] == "PRIVATE" \
				and utils.custom_key_exists("ignore_private", CONFIG_DATA):
					pass
				else:
					foundany = True
					if result["data"]["vsHistoryDetail"]["judgement"] == "WIN":
						outcome = "Victory"
					elif result["data"]["vsHistoryDetail"]["judgement"] in ("LOSE", "DEEMED_LOSE", "EXEMPTED_LOSE"):
						outcome = "Defeat"
					else:
						outcome = "Draw"
					splatfest_match = True if result["data"]["vsHistoryDetail"]["vsMode"]["mode"] == "FEST" else False
					if splatfest_match: # keys will exist
						our_team_name = result["data"]["vsHistoryDetail"]["myTeam"]["festTeamName"]
						their_team_name = result["data"]["vsHistoryDetail"]["otherTeams"][0]["festTeamName"]
						# works for tricolor too, since all teams would be the same
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
					if shortname == "d'Alfonsino": # lol franch
						shortname = "Museum"
					elif shortname == "Co.":
						shortname = "Cargo"
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
				result_post = requests.post(iksm.GRAPHQL_URL,
					data=utils.gen_graphql_body(utils.translate_rid["CoopHistoryDetailQuery"], "coopHistoryDetailId", num),
					headers=headbutt(forcelang='en-US'),
					cookies=dict(_gtoken=GTOKEN))
				result = json.loads(result_post.text)

				if result["data"]["coopHistoryDetail"]["jobPoint"] is None \
				and utils.custom_key_exists("ignore_private_jobs", CONFIG_DATA): # works pre- and post-2.0.0
					pass
				else:
					foundany = True
					outcome = "Clear" if result["data"]["coopHistoryDetail"]["resultWave"] == 0 else "Defeat"
					if outcome == "Clear":
						job_successes += 1
					else:
						job_failures += 1

					stagename = result["data"]["coopHistoryDetail"]["coopStage"]["name"]
					shortname = stagename.split(" ")[-1] # fine for salmon run stage names too
					endtime = utils.epoch_time(result["data"]["coopHistoryDetail"]["playedTime"])

					dt = datetime.datetime.fromtimestamp(endtime).strftime('%I:%M:%S %p').lstrip("0")
					print(f"New job result detected at {dt}! ({shortname}, {outcome})")
					cached_jobs.append(num)
					post_result(result, True, isblackout, istestrun) # True = is monitoring mode

	return which, cached_battles, cached_jobs, battle_wins, battle_losses, battle_draws, splatfest_wins, splatfest_losses, splatfest_draws, mirror_matches, job_successes, job_failures, foundany


def monitor_battles(which, secs, isblackout, istestrun, skipprefetch):
	'''Monitors SplatNet endpoint(s) for changes (new results) and uploads them (-M flag).'''

	if DEBUG:
		print(f"* monitoring mode start - calling fetch_json() w/ which={which}")
	# ! fetch from online - no 'specific' = should all be within 'latest'
	cached_battles, cached_jobs = fetch_json(which, separate=True, numbers_only=True, printout=True, skipprefetch=skipprefetch)
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
	print(f"Waiting for new {utils.set_noun(which)}... (checking every {mins} minute{'s' if mins != '1' else ''})")

	try:
		while True:
			for i in range(secs, -1, -1):
				sys.stdout.write(f"Press Ctrl+C to exit. {i} ")
				sys.stdout.flush()
				time.sleep(1)
				sys.stdout.write("\r")

			print("Checking for new results...", end='\r')
			input_params = [
				which,
				cached_battles, cached_jobs,
				battle_wins, battle_losses, battle_draws,
				splatfest_wins, splatfest_losses, splatfest_draws, mirror_matches,
				job_successes, job_failures,
				isblackout, istestrun
			]
			which, cached_battles, cached_jobs, battle_wins, battle_losses, battle_draws, splatfest_wins, splatfest_losses, splatfest_draws, mirror_matches, job_successes, job_failures, foundany=check_for_new_results(*input_params)

	except KeyboardInterrupt:
		print(f"\n\nChecking to see if there are unuploaded {utils.set_noun(which)} before exiting...")

		input_params = [
			which,
			cached_battles, cached_jobs,
			battle_wins, battle_losses, battle_draws,
			splatfest_wins, splatfest_losses, splatfest_draws, mirror_matches,
			job_successes, job_failures,
			isblackout, istestrun
		]
		which, cached_battles, cached_jobs, battle_wins, battle_losses, battle_draws, splatfest_wins, splatfest_losses, splatfest_draws, mirror_matches, job_successes, job_failures, foundany=check_for_new_results(*input_params)

		noun = utils.set_noun(which)
		if foundany:
			print(f"Successfully uploaded remaining {noun}.")
		else:
			print(f"No remaining {noun} found.")

		print("\n== SESSION REPORT ==")
		if which in ("ink", "both"):
			if battle_draws == 0:
				print(f"Battles: {battle_wins} win{'' if battle_wins == 1 else 's'} and " \
					f"{battle_losses} loss{'' if battle_losses == 1 else 'es'}.")
			else:
				print(f"Battles: {battle_wins} win{'' if battle_wins == 1 else 's'}, " \
					f"{battle_losses} loss{'' if battle_losses == 1 else 'es'}, and " \
					f"{battle_draws} draw{'' if battle_draws == 1 else 's'}.")

			if splatfest_wins + splatfest_losses + splatfest_draws > 0:
				if splatfest_draws == 0:
					print(f"Splatfest: {splatfest_wins} win{'' if splatfest_wins == 1 else 's'} and " \
						f"{splatfest_losses} loss{'' if splatfest_losses == 1 else 'es'} against the other Splatfest teams.")
				else:
					print(f"Splatfest: {splatfest_wins} win{'' if splatfest_wins == 1 else 's'}, " \
						f"{splatfest_losses} loss{'' if splatfest_losses == 1 else 'es'}, and " \
						f"{splatfest_draws} draw{'' if splatfest_draws == 1 else 's'} against the other Splatfest teams.")

				print(f"{mirror_matches} mirror match{'' if mirror_matches == 1 else 'es'} against your Splatfest team.")

		if which in ("salmon", "both"):
			print(f"Salmon Run: {job_successes} success{'' if job_successes == 1 else 'es'} and " \
				f"{job_failures} failure{'' if job_failures == 1 else 's'}.")

		print("Bye!")


class SquidProgress:
	'''Displays an animation of a squid swimming while waiting. :)'''

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


def export_seed_json(skipprefetch=False):
	'''Export a JSON file for use with Lean's seed checker at https://leanny.github.io/splat3seedchecker/.'''

	try:
		import pymmh3 as mmh3
	except ModuleNotFoundError:
		print("This function requires a Python module you don't have installed. " \
			"Please run " + '`\033[91m' + "pip install -r requirements.txt" + '\033[0m`' + " and try again.")
		sys.exit(1)

	if not skipprefetch:
		prefetch_checks(printout=True)

	sha = utils.translate_rid["MyOutfitCommonDataEquipmentsQuery"]
	outfit_post = requests.post(iksm.GRAPHQL_URL, data=utils.gen_graphql_body(sha),
		headers=headbutt(), cookies=dict(_gtoken=GTOKEN))

	sha = utils.translate_rid["LatestBattleHistoriesQuery"]
	history_post = requests.post(iksm.GRAPHQL_URL, data=utils.gen_graphql_body(sha),
		headers=headbutt(), cookies=dict(_gtoken=GTOKEN))

	if outfit_post.status_code != 200 or history_post.status_code != 200:
		print("Could not reach SplatNet 3. Exiting.")
		sys.exit(1)
	try:
		outfit = json.loads(outfit_post.text)
		history = json.loads(history_post.text)
	except:
		print("Ill-formatted JSON file received. Exiting.")
		sys.exit(1)

	try:
		pid = history["data"]["latestBattleHistories"]["historyGroupsOnlyFirst"]["nodes"][0]["historyDetails"]["nodes"][0]["player"]["id"]
		# VsPlayer-u-<20 char long player id>:RECENT:<YYYYMMDD>T<HHMMSS>_<UUID>:u-<same player id as earlier>
		s = utils.b64d(pid)
		r = s.split(":")[-1]
	except KeyError: # no recent battles (mr. grizz is pleased)
		try:
			sha = utils.translate_rid["CoopHistoryQuery"]
			history_post = requests.post(iksm.GRAPHQL_URL, data=utils.gen_graphql_body(sha),
				headers=headbutt(), cookies=dict(_gtoken=GTOKEN))

			if history_post.status_code != 200:
				print("Could not reach SplatNet 3. Exiting.")
				sys.exit(1)
			try:
				history = json.loads(history_post.text)
			except:
				print("Ill-formatted JSON file received. Exiting.")
				sys.exit(1)

			pid = history["data"]["coopResult"]["historyGroupsOnlyFirst"]["nodes"][0]["historyDetails"]["nodes"][0]["id"]
			# CoopHistoryDetail-u-<20 char long player id>:<YYYYMMDD>T<HHMMSS>_<UUID>
			s = utils.b64d(pid)
			r = s.split(":")[0].replace("CoopHistoryDetail-", "")
		except KeyError:
			r = ""

	h = mmh3.hash(r)&0xFFFFFFFF # make positive
	key = base64.b64encode(bytes([k^(h&0xFF) for k in bytes(r, "utf-8")]))
	t = int(time.time())

	with open(os.path.join(os.getcwd(), f"gear_{t}.json"), "x") as fout:
		json.dump({"key": key.decode("utf-8"), "h": h, "timestamp": t, "gear": outfit}, fout)

	print(f"gear_{t}.json has been exported.")


def parse_arguments():
	'''Setup for command-line options.'''

	parser = argparse.ArgumentParser()
	srgroup = parser.add_mutually_exclusive_group()
	parser.add_argument("-M", dest="N", required=False, nargs="?", action="store",
		help="monitoring mode; pull data every N secs (default: 300)", const=300)
	parser.add_argument("-m", dest="N", required=False, nargs="?", action="store",
		help=argparse.SUPPRESS, const=300)
	parser.add_argument("-r", required=False, action="store_true",
		help="check for & upload battles/jobs missing from stat.ink")
	srgroup.add_argument("-nsr", required=False, action="store_true",
		help="do not check for Salmon Run jobs")
	srgroup.add_argument("-osr", required=False, action="store_true",
		help="only check for Salmon Run jobs")
	parser.add_argument("--blackout", required=False, action="store_true",
		help="remove player names from uploaded scoreboard data")
	parser.add_argument("-o", required=False, action="store_true",
		help="export all possible results to local files")
	parser.add_argument("-i", dest="path", nargs=2, required=False,
		help="upload local results: `-i (coop_)results/ overview.json`")
	parser.add_argument("-t", required=False, action="store_true",
		help="dry run for testing (won't post to stat.ink)")
	parser.add_argument("--getseed", required=False, action="store_true",
		help="export JSON for gear & Shell-Out Machine seed checker")
	parser.add_argument("--skipprefetch", required=False, action="store_true", help=argparse.SUPPRESS)
	return parser.parse_args()


def main():
	'''Main process, including I/O and setup.'''

	print('\033[93m\033[1m' + "s3s" + '\033[0m\033[93m' + f" v{A_VERSION}" + '\033[0m')

	# argparse setup
	################
	parser_result = parse_arguments()

	# regular args
	n_value     = parser_result.N
	check_old   = parser_result.r
	only_ink    = parser_result.nsr # ink battles ONLY
	only_salmon = parser_result.osr # salmon run ONLY
	blackout    = parser_result.blackout
	getseed     = parser_result.getseed

	# testing/dev stuff
	test_run     = parser_result.t            # send to stat.ink as dry run
	file_paths   = parser_result.path         # intended for results/ or coop_results/ AND overview.json
	outfile      = parser_result.o            # output to local files
	skipprefetch = parser_result.skipprefetch # skip prefetch checks to ensure token validity

	# setup
	#######
	check_for_updates()
	if not getseed:
		check_statink_key()
	set_language()

	# i/o checks
	############
	if getseed and len(sys.argv) > 2 and "--skipprefetch" not in sys.argv:
		print("Cannot use --getseed with other arguments. Exiting.")
		sys.exit(0)

	elif getseed:
		export_seed_json(skipprefetch)
		sys.exit(0)

	elif only_ink and only_salmon:
		print("That doesn't make any sense! :) Exiting.")
		sys.exit(0)

	elif outfile and len(sys.argv) > 2 and "--skipprefetch" not in sys.argv:
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

	# export results to file: -o flag
	#################################
	if outfile:
		if not skipprefetch:
			prefetch_checks(printout=True)
		print("Fetching your JSON files to export locally. This might take a while...")
		# ! fetch from online - fetch_json() calls prefetch_checks() to gen or check tokens
		parents, results, coop_results = fetch_json("both", separate=True, exportall=True, specific=True, skipprefetch=True)

		cwd = os.getcwd()
		if utils.custom_key_exists("old_export_format", CONFIG_DATA):
			export_dir = os.path.join(cwd, f'export-{int(time.time())}')
			overview_filename = "overview.json"
		else:
			export_dir = os.path.join(cwd, 'exports')
			utc_time = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
			overview_filename = f'overview-{utc_time}.json'
		if not os.path.exists(export_dir):
			os.makedirs(export_dir)

		print()
		if parents is not None:
			with open(os.path.join(cwd, export_dir, overview_filename), "x") as fout:
				json.dump(parents, fout)
				print(f'Created {overview_filename} with general info about battle/job stats.')

		if results is not None:
			if utils.custom_key_exists("old_export_format", CONFIG_DATA):
				with open(os.path.join(cwd, export_dir, "results.json"), "x") as fout:
					json.dump(results, fout)
					print("Created results.json with recent battles (up to 50 per type).")
			else:
				results_dir = os.path.join(export_dir, 'results')
				if not os.path.exists(results_dir):
					os.makedirs(results_dir)

				for result in results:
					filename = result["data"]["vsHistoryDetail"]["playedTime"].replace("-", "").replace(":", "") + ".json"
					out_path = os.path.join(results_dir, filename)
					if not os.path.exists(out_path):
						with open(out_path, "x") as fout:
							json.dump(result, fout)
				print("Updated results directory with recent battles (up to 50 per type).")

		if coop_results is not None:
			if utils.custom_key_exists("old_export_format", CONFIG_DATA):
				with open(os.path.join(cwd, export_dir, "coop_results.json"), "x") as fout:
					json.dump(coop_results, fout)
					print("Created coop_results.json with recent Salmon Run jobs (up to 50).")
			else:
				coop_results_dir = os.path.join(export_dir, 'coop_results')
				if not os.path.exists(coop_results_dir):
					os.makedirs(coop_results_dir)

				for coop_result in coop_results:
					filename = coop_result["data"]["coopHistoryDetail"]["playedTime"].replace("-", "").replace(":", "") + ".json"
					out_path = os.path.join(coop_results_dir, filename)
					if not os.path.exists(out_path):
						with open(out_path, "x") as fout:
							json.dump(coop_result, fout)
				print("Updated coop_results directory with recent Salmon Run jobs (up to 50).")

		print("\nHave fun playing Splatoon 3! :) Bye!")
		sys.exit(0)

	# manual json upload: -i flag
	#############################
	if file_paths: # 2 paths in list
		if not utils.custom_key_exists("old_export_format", CONFIG_DATA):
			if os.path.dirname(os.path.join(file_paths[0], ''))[-7:] != "results" \
			or os.path.basename(file_paths[1])[:8] != "overview":
				print("Must pass in " + '\033[91m' + "results/" + '\033[0m' + " or " + \
					'\033[91m' + "coop_results/" + '\033[0m' + " followed by an " +
					'\033[91m' + "overview.json" + '\033[0m' + ". Exiting.")
				sys.exit(1)
		for file_path in file_paths:
			if not os.path.exists(file_path):
				path_type = "File" if file_path.endswith(".json") else "Directory"
				print(f"{path_type} {file_path} does not exist!")
				sys.exit(1)

		# argument #1 - results folder or file
		if not utils.custom_key_exists("old_export_format", CONFIG_DATA):
			data = []
			for json_file in os.listdir(file_paths[0]):
				if json_file.endswith('.json'): # just in case
					with open(os.path.join(file_paths[0], json_file)) as data_file:
						contents = json.load(data_file)
						data.append(contents)
		else: #old method
			with open(file_paths[0]) as data_file:
				try:
					data = json.load(data_file)
				except ValueError:
					print(f"Could not decode JSON object in {os.path.basename(file_paths[0])}.")
					sys.exit(1)

		# argument #2 - overview.json
		with open(file_paths[1]) as data_file:
			try:
				overview_file = json.load(data_file)
			except ValueError:
				print("Could not decode JSON object in your overview.json.")
				sys.exit(1)
		data.reverse()

		# only upload unuploaded results
		auth = {'Authorization': f'Bearer {API_KEY}'}
		resp_b = requests.get("https://stat.ink/api/v3/s3s/uuid-list?lobby=adaptive", headers=auth)
		resp_j = requests.get("https://stat.ink/api/v3/salmon/uuid-list", headers=auth)
		try:
			statink_uploads = json.loads(resp_b.text)
			statink_uploads.extend(json.loads(resp_j.text))
		except:
			print(f"Encountered an error while checking recently-uploaded data. Is stat.ink down?")
			sys.exit(1)

		to_upload = []
		for result in data:
			try: # ink battle
				if result["data"]["vsHistoryDetail"] is not None:
					full_id = utils.b64d(result["data"]["vsHistoryDetail"]["id"])
					old_uuid = full_id[-36:] # not unique because nintendo hates us
					new_uuid = str(uuid.uuid5(utils.S3S_NAMESPACE, full_id[-52:]))

					if new_uuid in statink_uploads:
						print("Skipping already-uploaded battle.")
						continue
					if old_uuid in statink_uploads:
						if not utils.custom_key_exists("force_uploads", CONFIG_DATA):
							print("Skipping already-uploaded battle (use the `force_uploads` config key to override).")
							continue
					to_upload.append(result)

			except KeyError: # salmon run job
				if result["data"]["coopHistoryDetail"] is not None:
					full_id = utils.b64d(result["data"]["coopHistoryDetail"]["id"])
					old_uuid = str(uuid.uuid5(utils.SALMON_NAMESPACE, full_id[-52:]))
					new_uuid = str(uuid.uuid5(utils.SALMON_NAMESPACE, full_id))

					if new_uuid in statink_uploads:
						print("Skipping already-uploaded job.")
						continue
					if old_uuid in statink_uploads:
						if not utils.custom_key_exists("force_uploads", CONFIG_DATA):
							print("Skipping already-uploaded job (use the `force_uploads` config key to override).")
							continue

					to_upload.append(result)

		if len(to_upload) == 0:
			print("Nothing to upload that isn't already on stat.ink.")
		else:
			post_result(to_upload, False, blackout, test_run, overview_data=overview_file) # one or multiple; monitoring mode = False
		sys.exit(0)

	# regular run
	#############
	which = "ink" if only_ink else "salmon" if only_salmon else "both"

	# if which in ("salmon", "both"):
	# 	update_salmon_profile() # not a thing for spl3, done on stat.ink's end

	if check_old:
		if which == "both":
			prefetch_checks(printout=True)
			skipprefetch = True
		check_if_missing(which, blackout, test_run, skipprefetch) # monitoring mode hasn't begun yet
		print()

	if secs != -1: # monitoring mode
		skipprefetch = True if skipprefetch or check_old else False
		monitor_battles(which, secs, blackout, test_run, skipprefetch) # skip prefetch checks if already done in -r

	elif not check_old: # regular mode (no -M) and did not just use -r
		if which == "both":
			print("Please specify whether you want to upload battle results (-nsr) or Salmon Run jobs (-osr). Exiting.")
			sys.exit(0)

		n = get_num_results(which)
		print("Pulling data from online...")

		# ! fetch from online
		try:
			results = fetch_json(which, numbers_only=True, printout=True, skipprefetch=skipprefetch)
		except json.decoder.JSONDecodeError:
			print("\nCould not fetch results JSON. Are your tokens invalid?")
			sys.exit(1)

		results = results[:n] # limit to n uploads
		results.reverse() # sort from oldest to newest
		noun = utils.set_noun(which)
		for hash_ in results:
			fetch_and_upload_single_result(hash_, noun, blackout, test_run) # not monitoring mode

	thread_pool.shutdown(wait=True)


if __name__ == "__main__":
	main()
