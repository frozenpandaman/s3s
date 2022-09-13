# s3s updater
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from builtins import input
import os.path
import requests
import re
try:
	from packaging import version
except ModuleNotFoundError as e:
	version = None
from subprocess import call


def check_s3s(A_VERSION):
	'''Checks the script version against the repo, reminding users to update if available.'''

	if version is None:
		# TODO: Since it is already needed, I consider the chances of it not existing to be zero.
		#       If so, add arguments (version), or ...
		print("\n!! Please re-run `pip install -r requirements.txt` (see readme for details). \n")
	try:
		latest_script = requests.get(
			"https://raw.githubusercontent.com/frozenpandaman/s3s/master/s3s.py")
		new_version = re.search(r'= "([\d.]*)"', latest_script.text).group(1)
		update_available = version.parse(
			new_version) != version.parse(A_VERSION)
		if update_available:
			print("\nThere is a new version (v{}) available.".format(
				new_version), end='')
			if os.path.isdir(".git"):  # git user
				update_now = input("\nWould you like to update now? [Y/n] ")
				if update_now == "" or update_now[0].lower() == "y":
					FNULL = open(os.devnull, "w")
					call(["git", "checkout", "."], stdout=FNULL, stderr=FNULL)
					call(["git", "checkout", "master"],
						 stdout=FNULL, stderr=FNULL)
					call(["git", "pull"], stdout=FNULL, stderr=FNULL)
					print("Successfully updated to v{}. Please restart s3s.".format(new_version))
					return True
				else:
					print("Remember to update later with `git pull` to get the latest version.\n")
			else:  # non-git user
				print(" Visit the site below to update:\nhttps://github.com/frozenpandaman/s3s\n")
	except:  # if there's a problem connecting to github - or can't access 'version' if 'packaging' not installed
		pass  # then we assume there's no update available


