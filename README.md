s3s 🦑
=====

**s3s** is a script that uploads _Splatoon 3_ battle data from the SplatNet 3 service (part of the Nintendo Switch Online app) to [stat.ink](https://stat.ink/), a site for recording, visualizing, and aggregating statistics from the *Splatoon* series of games.

Looking to track your _Splatoon 2_ gameplay? See **[splatnet2statink](https://github.com/frozenpandaman/splatnet2statink)**. (日本語版セットアップ手順 & 中文版的安装说明)

### What's coming?
 - [ ] Full automation of SplatNet cookie generation via user log-in
 - [ ] Ability to parse & upload complete battle stats
 - [ ] Monitoring for new battle & Salmon Run job results in real-time
 - [ ] Support for all available game languages
 - [ ] Modular design to support [IkaLog3](https://github.com/hasegaw/IkaLog3) and other tools
 - [ ] Downloadable, pre-packaged program executables

---

## Usage 🐙
```
$ python s3s.py [-M [N]] [-r] [-nsr | -osr] [--blackout]
```

The `-M` flag runs the script in monitoring mode, uploading new battles/jobs as you play, checking for new results every `N` seconds; if no `N` is provided, it defaults to 300 (5 minutes).

The `-r` flag checks for & uploads any battles/jobs present on SplatNet 3 that haven't yet been uploaded.

The `-nsr` flag makes Salmon Run jobs **not** be monitored or uploaded. Use this if you're playing Turf War/Ranked modes only.

The `-osr` flag, conversely, makes **only** Salmon Run jobs be monitored or uploaded.

The `--blackout` flag blacks out other players' names on scoreboard result images and in uploaded data.

### Example usage

Running `python s3s.py -M -r` uploads all recent Turf War/Ranked battles _and_ Salmon Run jobs not already present on stat.ink, and then continues in monitoring mode, checking for new results every 5 minutes.

Running `python s3s.py -M 900 -osr` monitors for new Salmon Run results, checking every 15 minutes.

## Setup instructions 🔰

1. Download and install Python 3. On Windows, grab the latest release from [Python.org](https://www.python.org/downloads/windows/) and check the option during setup to add it to your PATH. On macOS, install [Homebrew](https://brew.sh/) and run `brew install python` from Terminal.

2. If you're on Windows, install [Git](https://git-scm.com/download/win) (pre-installed on macOS and Linux).

3. Download the script from the command line (macOS: Terminal; Windows: Command Prompt/PowerShell) by running `git clone https://github.com/frozenpandaman/s3s.git`.

4. Navigate to the newly-created directory (`cd s3s/`) and install the required Python libraries by running `pip install -r requirements.txt`. On Windows, you may have to use `python -m pip` instead.

5. Running the script for the first time will prompt you to enter your stat.ink API Token (available in [settings](https://stat.ink/profile)). If you're playing _Splatoon 3_ in a language other than English, you may enter your language code (locale) as well.

**NOTE: Read the "Cookie generation" section below before proceeding. [→](#cookie-generation-)**

6. You will then be asked to navigate to a specific URL on Nintendo.com, log in, and follow simple instructions to obtain your `session_token`; this will be used to generate a `bulletToken`. If you are opting against automatic cookie generation, enter "skip" for this step, at which point you will be asked to manually input your `bulletToken` instead (see the [mitmproxy instructions](https://github.com/frozenpandaman/s3s/wiki/mitmproxy-instructions)).

    This cookie (used to access your SplatNet battle results) along with your stat.ink API key and language will automatically be saved into `config.txt` for you. You're now ready to upload battles!

Have any questions, issues, or suggestions? Feel free to message me on [Twitter](https://twitter.com/frozenpandaman) or create an [issue](https://github.com/frozenpandaman/s3s/issues) here.

質問があれば、ツイッター([@frozenpandaman](https://twitter.com/frozenpandaman))で連絡してください。日本語OK。

### Accessing SplatNet 3 from your browser

coming soon

## Cookie generation 🍪

For s3s to work, [cookies](https://en.wikipedia.org/wiki/HTTP_cookie) known as `GameWebToken` and `bulletToken` are required to access SplatNet. These tokens may be obtained automatically, using the script, or manually via the official Nintendo Switch Online app. Please read the following sections carefully to decide whether or not you want to use automatic cookie generation.

### Automatic

Automatic cookie generation involves making a *secure request to a non-Nintendo server with minimal, non-identifying information*. We aim to be 100% transparent about this and provide in-depth information on security and privacy. Users who feel uncomfortable with this may opt to manually acquire their cookie instead.

**Privacy statement:** No identifying information is ever sent to the [imink API](https://status.imink.app/). Usernames and passwords are far removed from where the API comes into play and are never readable by anyone but you, and returned hash values do not contain meaningful information about your account. It is not possible to use either sent or stored data to identify which account/user performed a request, to view any identifying information about a user, or to gain access to an account. See the [imink API Privacy Policy](https://github.com/JoneWang/imink/wiki/Privacy-Policy) and [Documentation](https://github.com/JoneWang/imink/wiki/imink-API-Documentation) for more information.

### Manual

Users who decide against automatic cookie generation may instead generate/retrieve `bulletToken`s manually via the SplatNet 3 service.

In this case, users must obtain their cookie from their phone – or an emulator – by intercepting their device's web traffic and entering it into s3s when prompted (or manually adding it to `config.txt` later). Follow the [mitmproxy instructions](https://github.com/frozenpandaman/s3s/wiki/mitmproxy-instructions) to obtain your token. To opt against automatic acquisition, type "skip" when prompted to enter the "Select this account" URL.

## License & copyleft statement 🏴

s3s is _free software_ licensed under [GPLv3](https://www.gnu.org/licenses/gpl-3.0.html). This means that you have _freedom_ – to run, modify, copy, share, and redistribute this work as you see fit, as long as derivative works are also distributed under these same or equivalent terms.

Copyright is a recent, confusing, and often unnecessary human invention. Libraries, for example, predate copyright by thousands of years, and their their integral role in the "promotion of science" and "encouragement of learning" was acknowledged even before the first copyright statutes were enacted. If the first human who had the idea of a hammer claimed it as their intellectual property, we wouldn't have gotten very far as a species. Please consider sharing your work openly with the world. _(statement adapted from [here](https://tspace.library.utoronto.ca/bitstream/1807/89456/1/Katz%20Copyright%2C%20Exhaustion.pdf) and [here](https://www2.hawaii.edu/~larkinrt/about/))_

While this is a free and open-source project, its license does require **attribution**. **If you are using any part of s3s, splatnet2statink, `iksm.py`, etc. in your project, _please provide a link back to this repository_**. I have spent over half a decade and hundreds of hours of my personal time on these projects for the Splatoon community – so, at the least, some credit would be appreciated. :) Thank you! –eli