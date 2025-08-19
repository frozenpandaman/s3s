"""
Extract gToken and bulletToken for Splatoon 3 NSO.
The result will be saved in config.txt.
"""

import logging
import json
import os
import sys
from mitmproxy import ctx
from mitmproxy.tools.main import mitmdump

config_path = os.path.join(os.path.dirname(__file__), "config.txt")

try:
	config_file = open(config_path, "r")
	CONFIG_DATA = json.load(config_file)
	config_file.close()
except (IOError, ValueError):
    print('Please run s3s.py first to generate the config file.')
    ctx.master.shutdown()
    sys.exit()

# SET GLOBALS
API_KEY       = CONFIG_DATA["api_key"]       # for stat.ink
USER_LANG     = CONFIG_DATA["acc_loc"][:5]   # user input
USER_COUNTRY  = CONFIG_DATA["acc_loc"][-2:]  # nintendo account info
GTOKEN        = CONFIG_DATA["gtoken"]        # for accessing splatnet - base64 json web token
BULLETTOKEN   = CONFIG_DATA["bullettoken"]   # for accessing splatnet - base64
SESSION_TOKEN = CONFIG_DATA["session_token"] # for nintendo login
F_GEN_URL     = CONFIG_DATA["f_gen"]         # endpoint for generating f (imink API by default)

class Splatoon3TokenExtractor:
    def __init__(self):
        #self.outfile = open("gtoken_bullettoken.txt", "w")
        self.web_service_token = None
        self.bullet_token = None

    def response(self, flow):
        path = flow.request.path
        if path.endswith('api/token'):
            logging.info(f"{flow.response}")
            obj = json.loads(flow.response.content.decode('utf-8'))
            self.web_service_token = obj["access_token"]
            logging.info(self.web_service_token)
        if path.endswith('bullet_tokens'):
            logging.info(f"{flow.response}") 
            obj = json.loads(flow.response.content.decode('utf-8'))
            self.bullet_token = obj["bulletToken"]
            logging.info(self.bullet_token)
        if self.web_service_token and self.bullet_token:
            # write into config file
            CONFIG_DATA["gtoken"] = self.web_service_token
            CONFIG_DATA["bullettoken"] = self.bullet_token
            config_file = open(config_path, "w")
            config_file.seek(0)
            config_file.write(json.dumps(CONFIG_DATA, indent=4, sort_keys=False, separators=(',', ': ')))
            config_file.close()
            ctx.master.shutdown()

addons = [Splatoon3TokenExtractor()]

def main():
	mitmdump(['-s', __file__, '~u GetWebServiceToken | ~u bullet_tokens', '--view-filter', '~u GetWebServiceToken | ~u bullet_tokens'])

if __name__ == "__main__":
	main()