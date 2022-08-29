# s3s

**`s3s`** is a script that uploads battle data from the SplatNet 3 service (part of the Nintendo Switch Online app) to [stat.ink](https://stat.ink/), a site for recording, visualizing, and aggregating statistics from the *Splatoon* series of games.

Looking to track your _Splatoon 2_ gameplay? See **[splatnet2statink](https://github.com/frozenpandaman/splatnet2statink)**.

### What's coming?
 - [ ] Full automation of SplatNet cookie generation via user log-in
 - [ ] Ability to parse & upload complete battle stats
 - [ ] Monitoring for new battle & Salmon Run job results in real-time
 - [ ] Support for all available game languages
 - [ ] Modular design to support [IkaLog3](https://github.com/hasegaw/IkaLog3) and other tools
 - [ ] Downloadable, pre-packaged program executables

---

## Usage
```
$ python s3s.py [-M [N]] [-r] [-nsr | -osr] [--blackout]
```

The `-M` flag runs the script in monitoring mode, uploading new battles/jobs as you play, checking for new results every `N` seconds; if no `N` is provided, it defaults to 300 (5 minutes).

The `-r` flag checks for & uploads any battles/jobs present on SplatNet 3 that haven't yet been uploaded to stat.ink.

The `-nsr` flag makes Salmon Run jobs **not** be monitored or uploaded. Use this if you're playing Turf War/Ranked modes only.

The `-osr` flag, conversely, makes **only** Salmon Run jobs be monitored or uploaded. Use this if you're not playing Turf War/Ranked modes.

The `--blackout` flag blacks out other players' names on scoreboard result images and doesn't send them to stat.ink.

### Example usage

Running `python s3s.py -M 900 -r` uploads all recent results (from both Turf War/Ranked and Salmon Run modes) not already present on stat.ink, and then continues in monitoring mode, checking for and uploading new battles/jobs every 15 minutes.

## Setup instructions

...
