s3s 🦑
=====

**s3s** is a script that uploads _Splatoon 3_ battle data from the SplatNet 3 service (part of the Nintendo Switch Online app) to [stat.ink](https://stat.ink/), a site for recording, visualizing, and aggregating statistics from the *Splatoon* series of games.

(ja) 日本語版セットアップ手順は[こちら](https://nerune-jp.com/splatoon3-statink/)、または[こちら](https://vanillasalt.net/2022/10/10/how-to-use-s3s/)。

(ko) 한국어 가이드는 [여기](https://github.com/cake-monotone/s3s)를 참조해 주세요.

Looking to track your _Splatoon 2_ gameplay? See **[splatnet2statink](https://github.com/frozenpandaman/splatnet2statink)**.

### Features
 - [x] Full automation of SplatNet token generation via user log-in
 - [x] Ability to parse & upload complete battle/job stats to stat.ink ([example profile](https://stat.ink/@frozenpandaman/spl3))
 - [x] Support for Salmon Run Next Wave and Big Run
 - [x] Support for Splatfest & Tricolor Turf War battles and Challenges
 - [x] Monitoring for new results in real-time & checking for missing/unuploaded results
 - [x] Flag to remove other players' names from results
 - [x] Support for all available game languages
 - [x] File exporting function for use with Lean's [seed checker tools](https://leanny.github.io/splat3seedchecker/)
 - [x] Modular design to support [IkaLog3](https://github.com/hasegaw/IkaLog3) and other tools

### What's coming?
 - [ ] Easier setup via downloadable, pre-packaged program executables (soon!)

---

## Usage 🐙
```
$ python s3s.py [-M [N]] [-r] [-nsr | -osr] [--blackout]
```

The `-M` flag runs the script in monitoring mode, uploading new matches as you play, checking for new results every `N` seconds; if no `N` is provided, it defaults to 300 (5 minutes).

The `-r` flag checks for & uploads any battles/jobs present on SplatNet 3 that haven't yet been uploaded.

The `-nsr` flag makes Salmon Run jobs **not** be monitored/uploaded. Use this if you're playing Lobby modes only.

The `-osr` flag, conversely, makes **only** Salmon Run jobs be monitored/uploaded. Use this if you're playing at Grizzco only.

The `--blackout` flag removes other players' names from uploaded scoreboard data.

Arguments for advanced usage (e.g. locally exporting data to JSON files, use with with Lean's [seed checker tools](https://leanny.github.io/splat3seedchecker/)) can be viewed using `--help`.

### Tips for using s3s

★ **On first run**, you'll want to use the `-r` flag to upload _all_ available data from SplatNet to stat.ink, i.e. up to 250 battles (50 of each type: Turf War, Anarchy, X, Challenge, and Private) and up to 50 recent Salmon Run jobs.

The suggested usage of s3s is in monitoring mode, where you run the script as you play the game and exit it once you're done playing. The command **`python s3s.py -r -M`** first looks to ensure there's no data missing from stat.ink (uploading it if so), and then continues in monitoring mode while checking for new results every 5 minutes.

More specific use cases can be specified using other flags (and [config keys](https://github.com/frozenpandaman/s3s/wiki/config-keys)). For example, if you're solely playing Salmon Run and only want to check for new results every 15 minutes, you would use `python s3s.py -osr -M 900`. If not using monitoring mode, `python s3s.py -r` should be run at least once every 50 matches to ensure no data is lost.

## Setup instructions 🔰

1. Download and install Python 3. On Windows, grab the latest release from [Python.org](https://www.python.org/downloads/windows/) and check the option during setup to add it to your PATH. On macOS, install [Homebrew](https://brew.sh/) and run `brew install python` from Terminal. Run `python --version` to verify the installation.

2. If you're on Windows, install [Git](https://git-scm.com/download/win) (pre-installed on macOS and Linux).

3. Download the script from the command line (macOS: Terminal; Windows: Command Prompt/PowerShell) by running `git clone https://github.com/frozenpandaman/s3s.git`.

4. Navigate to the newly-created directory (type `cd s3s/`) and install the required Python libraries by running `pip install -r requirements.txt`. On Windows, you may have to use `python -m pip` instead.

5. Running the script for the first time (see the "Usage" section above [→](#usage-)) will prompt you to enter your stat.ink API Token (available in [settings](https://stat.ink/profile)). If you're playing the game in a language other than English, you may enter your language code (locale) as well.

NOTE: Read the "Token generation" section below before proceeding. [→](#token-generation-)

6. You will then be asked to navigate to a specific URL on Nintendo.com, log in, and follow simple instructions to obtain your `session_token`; this will be used to generate a `gtoken` and `bulletToken`. If you are opting against automatic token generation, enter "skip" for this step, at which point you will be asked to manually input your two tokens instead (see the [mitmproxy instructions](https://github.com/frozenpandaman/s3s/wiki/mitmproxy-instructions)).

    These tokens (used to access your SplatNet battle results) along with your stat.ink API key & language will be saved into `config.txt` for you. You're now ready to upload battles!

Have any questions, problems, or suggestions? [Create an issue](https://github.com/frozenpandaman/s3s/issues) here or contact me on [Twitter](https://twitter.com/frozenpandaman). **Please do not raise issues via Discord. It is important for discussion on the internet to be public, indexable, and searchable, able to be shared freely and benefit others – not locked behind a private platform. [Here](https://v21.io/blog/how-to-find-things-online)'s a great article about this!**

質問があれば、ツイッター([@frozenpandaman](https://twitter.com/frozenpandaman))で連絡してください。日本語OK。

### Accessing SplatNet 3 from your browser

If you wish to access SplatNet 3 from your computer rather than via the NSO phone app, or if you don't have a smartphone, follow [this s3s wiki article](https://github.com/frozenpandaman/s3s/wiki/in%E2%80%90browser-splatnet-3) to enable the use of SplatNet in-browser.

SplatNet 3 can be used in any available game language. You can even enter QR codes on the web version of the app via the list of available ones [here](https://github.com/frozenpandaman/s3s/wiki/list-of-qr-codes)!

*Splatoon 3* stage rotation information, Splatfest data, and current SplatNet gear are viewable at [splatoon3.ink](https://splatoon3.ink/).

## Token generation 🪙

For s3s to work, [tokens](https://en.wikipedia.org/wiki/Access_token) known as `gtoken` and `bulletToken` are needed to access SplatNet. These tokens may be obtained automatically, using the script, or manually via the official Nintendo Switch Online app. Please read the following sections carefully to decide whether or not you want to use automatic token generation.

### Automatic

Automatic token generation involves making a *secure request to a non-Nintendo server with minimal, non-identifying information*. We aim to be 100% transparent about this and provide in-depth information on security and privacy. Users who feel uncomfortable with this may opt to manually acquire their tokens instead.

**Privacy statement:** No identifying information is ever sent to the [imink API](https://status.imink.app/). Usernames and passwords are far removed from where the API comes into play and are never readable by anyone but you, and returned values do not contain any meaningful information about your account. It is not possible to use either sent or stored data to identify which account/user performed a request, to view identifying information about a user, or to gain access to an account. See the [imink API Privacy Policy](https://github.com/JoneWang/imink/wiki/Privacy-Policy) and [Documentation](https://github.com/JoneWang/imink/wiki/imink-API-Documentation) for more information.

Alternatively, you can use [nsotokengen](https://github.com/clovervidia/nsotokengen) or [nxapi-znca-api](https://github.com/samuelthomas2774/nxapi-znca-api) as a drop-in replacement (customizable in `config.txt`) to generate tokens locally, i.e. without calls to a third-party API.

### Manual

Users who decide against using automatic token generation may instead retrieve tokens manually via SplatNet 3.

In this case, users must obtain tokens from their phone – or an emulator – by intercepting their device's web traffic and entering the tokens into s3s when prompted (or manually adding them to `config.txt` later). Follow the [mitmproxy instructions](https://github.com/frozenpandaman/s3s/wiki/mitmproxy-instructions) to obtain your tokens. To opt for manual token entry, type "skip" when prompted to enter the "Select this account" URL.

## License & copyleft statement 🏴

s3s is _free software_ licensed under [GPLv3](https://www.gnu.org/licenses/gpl-3.0.html). This means that you have _freedom_ – to run, modify, copy, share, and redistribute this work as you see fit, as long as derivative works are also distributed under these same or equivalent terms.

Copyright is a recent, confusing, and often unnecessary human invention. Libraries, for example, predate copyright by thousands of years, and their integral role in the "promotion of science" and "encouragement of learning" was acknowledged even before the first copyright statutes were enacted. If the first human who had the idea of a hammer claimed it as their intellectual property, we wouldn't have gotten very far as a species. Please consider sharing your work openly with the world. _(statement adapted from [here](https://tspace.library.utoronto.ca/bitstream/1807/89456/1/Katz%20Copyright%2C%20Exhaustion.pdf) and [here](https://rickey.info/about/))_

While this is a free/libre and open-source project, its license does require **attribution**. **If you are using any part of s3s, splatnet2statink, `iksm.py`, etc. in your project, _please provide a link back to this repository_**. I have spent over half a decade and hundreds of hours of my personal time on these projects for the Splatoon community – so, at the least, some credit would be nice. :) Donations, via the "Sponsor" button at the top or links in the sidebar, are also greatly appreciated. Thank you, and stay fresh! –eli ＜コ:彡