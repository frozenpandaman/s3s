# (ↄ) 2017-2023 eli fessler (frozenpandaman), clovervidia
# https://github.com/frozenpandaman/s3s
# License: GPLv3

import base64, datetime, json, re, sys, uuid
import requests
from bs4 import BeautifulSoup
import iksm

SPLATNET3_URL    = iksm.SPLATNET3_URL
GRAPHQL_URL      = f'{SPLATNET3_URL}/api/graphql'
S3S_NAMESPACE    = uuid.UUID('b3a2dbf5-2c09-4792-b78c-00b548b70aeb')
SALMON_NAMESPACE = uuid.UUID('f1911910-605e-11ed-a622-7085c2057a9d')

SUPPORTED_KEYS = [
	"ignore_private",
	"ignore_private_jobs",
	"app_user_agent",
	"force_uploads",
	"errors_pass_silently",
	"old_export_format"
]

# SHA256 hash database for SplatNet 3 GraphQL queries
# full list: https://github.com/samuelthomas2774/nxapi/discussions/11#discussioncomment-3614603
translate_rid = {
	'HomeQuery':                   '51fc56bbf006caf37728914aa8bc0e2c86a80cf195b4d4027d6822a3623098a8', # vars: blank
	'LatestBattleHistoriesQuery':  'b24d22fd6cb251c515c2b90044039698aa27bc1fab15801d83014d919cd45780', # blank (query1)
	'RegularBattleHistoriesQuery': '2fe6ea7a2de1d6a888b7bd3dbeb6acc8e3246f055ca39b80c4531bbcd0727bba', # blank (query1)
	'BankaraBattleHistoriesQuery': '9863ea4744730743268e2940396e21b891104ed40e2286789f05100b45a0b0fd', # blank (query1)
	'PrivateBattleHistoriesQuery': 'fef94f39b9eeac6b2fac4de43bc0442c16a9f2df95f4d367dd8a79d7c5ed5ce7', # blank (query1)
	'XBattleHistoriesQuery':       'eb5996a12705c2e94813a62e05c0dc419aad2811b8d49d53e5732290105559cb', # blank (query1)
	'EventBattleHistoriesQuery':   'e47f9aac5599f75c842335ef0ab8f4c640e8bf2afe588a3b1d4b480ee79198ac', # blank (query1)
	'VsHistoryDetailQuery':        'f893e1ddcfb8a4fd645fd75ced173f18b2750e5cfba41d2669b9814f6ceaec46', # vsResultId (query2)
	'CoopHistoryQuery':            '0f8c33970a425683bb1bdecca50a0ca4fb3c3641c0b2a1237aedfde9c0cb2b8f', # blank (query1)
	'CoopHistoryDetailQuery':      '824a1e22c4ad4eece7ad94a9a0343ecd76784be4f77d8f6f563c165afc8cf602', # coopHistoryDetailId (query2)
	'MyOutfitCommonDataEquipmentsQuery': '45a4c343d973864f7bb9e9efac404182be1d48cf2181619505e9b7cd3b56a6e8'  # for lean's seed checker
}


def translate_gear_ability(url):
	'''Given a URL, returns the gear ability string corresponding to the filename hash.'''

	hash_map = {
		'5c98cc37d2ce56291a7e430459dc9c44d53ca98b8426c5192f4a53e6dd6e4293': 'ink_saver_main',
		'11293d8fe7cfb82d55629c058a447f67968fc449fd52e7dd53f7f162fa4672e3': 'ink_saver_sub',
		'29b845ea895b931bfaf895e0161aeb47166cbf05f94f04601769c885d019073b': 'ink_recovery_up',
		'3b6c56c57a6d8024f9c7d6e259ffa2e2be4bdf958653b834e524ffcbf1e6808e': 'run_speed_up',
		'087ffffe40c28a40a39dc4a577c235f4cc375540c79dfa8ede1d8b63a063f261': 'swim_speed_up',
		'e8668a2af7259be74814a9e453528a3e9773435a34177617a45bbf79ad0feb17': 'special_charge_up',
		'e3154ab67494df2793b72eabf912104c21fbca71e540230597222e766756b3e4': 'special_saver',
		'fba267bd56f536253a6bcce1e919d8a48c2b793c1b554ac968af8d2068b22cab': 'special_power_up',
		'aaa9b7e95a61bfd869aaa9beb836c74f9b8d4e5d4186768a27d6e443c64f33ce': 'quick_respawn',
		'138820ed46d68bdf2d7a21fb3f74621d8fc8c2a7cb6abe8d7c1a3d7c465108a7': 'quick_super_jump',
		'9df9825e470e00727aa1009c4418cf0ace58e1e529dab9a7c1787309bb25f327': 'sub_power_up',
		'db36f7e89194ed642f53465abfa449669031a66d7538135c703d3f7d41f99c0d': 'ink_resistance_up',
		'664489b24e668ef1937bfc9a80a8cf9cf4927b1e16481fa48e7faee42122996d': 'sub_resistance_up',
		'1a0c78a1714c5abababd7ffcba258c723fefade1f92684aa5f0ff7784cc467d0': 'intensify_action',
		'85d97cd3d5890b80e020a554167e69b5acfa86e96d6e075b5776e6a8562d3d4a': 'opening_gambit',
		'd514787f65831c5121f68b8d96338412a0d261e39e522638488b24895e97eb88': 'last_ditch_effort',
		'aa5b599075c3c1d27eff696aeded9f1e1ddf7ae3d720268e520b260db5600d60': 'tenacity',
		'748c101d23261aee8404c573a947ffc7e116a8da588c7371c40c4f2af6a05a19': 'comeback',
		'2c0ef71abfb3efe0e67ab981fc9cd46efddcaf93e6e20da96980079f8509d05d': 'ninja_squid',
		'de15cad48e5f23d147449c70ee4e2973118959a1a115401561e90fc65b53311b': 'haunt',
		'56816a7181e663b5fedce6315eb0ad538e0aadc257b46a630fcfcc4a16155941': 'thermal_ink',
		'de0d92f7dfed6c76772653d6858e7b67dd1c83be31bd2324c7939105180f5b71': 'respawn_punisher',
		'0d6607b6334e1e84279e482c1b54659e31d30486ef0576156ee0974d8d569dbc': 'ability_doubler',
		'f9c21eacf6dbc1d06edbe498962f8ed766ab43cb1d63806f3731bf57411ae7b6': 'stealth_jump',
		'9d982dc1a7a8a427d74df0edcebcc13383c325c96e75af17b9cdb6f4e8dafb24': 'object_shredder',
		'18f03a68ee64da0a2e4e40d6fc19de2e9af3569bb6762551037fd22cf07b7d2d': 'drop_roller',
		'dc937b59892604f5a86ac96936cd7ff09e25f18ae6b758e8014a24c7fa039e91': None
	}

	for entry in hash_map:
		if entry in url:
			return hash_map[entry]


def set_noun(which):
	'''Returns the term to be used when referring to the type of results in question.'''

	if which == "both":
		return "battles/jobs"
	elif which == "salmon":
		return "jobs"
	else: # "ink"
		return "battles"


def convert_color(rgbadict):
	'''Given a dict of numbers from 0.0 - 1.0, converts these into a RGBA hex color format (without the leading #).'''

	r = int(255 * rgbadict["r"])
	g = int(255 * rgbadict["g"])
	b = int(255 * rgbadict["b"])
	a = int(255 * rgbadict["a"])
	return f"{r:02x}{g:02x}{b:02x}{a:02x}"


def convert_tricolor_role(string):
	'''Given a SplatNet 3 Tricolor Turf War team role, convert it to the stat.ink string format.'''

	if string == "DEFENSE":
		return "defender"
	else: # ATTACK1 or ATTACK2
		return "attacker"


def b64d(string):
	'''Base64-decodes a string and cuts off the SplatNet prefix.'''

	thing_id = base64.b64decode(string).decode('utf-8')
	thing_id = thing_id.replace("VsStage-", "")
	thing_id = thing_id.replace("VsMode-", "")
	thing_id = thing_id.replace("CoopStage-", "")
	thing_id = thing_id.replace("CoopGrade-", "")
	thing_id = thing_id.replace("CoopEnemy-", "")
	thing_id = thing_id.replace("CoopEventWave-", "")
	thing_id = thing_id.replace("CoopUniform-", "")
	thing_id = thing_id.replace("SpecialWeapon-", "")

	if "Weapon-" in thing_id:
		thing_id = thing_id.replace("Weapon-", "")
		if len(thing_id) == 5 and thing_id[:1] == "2" and thing_id[-3:] == "900": # grizzco weapon ID from a hacker
			return ""

	if thing_id[:15] == "VsHistoryDetail" or thing_id[:17] == "CoopHistoryDetail" or thing_id[:8] == "VsPlayer":
		return thing_id # string
	else:
		return int(thing_id) # integer


def epoch_time(time_string):
	'''Converts a playedTime string into an integer representing the epoch time.'''

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
