User-scope systemd timer for the daily run (`ingest.py daily`: today's snapshots, the last week of
prices, the engines, then `ingest.py outcomes`). Install once:

    mkdir -p ~/.config/systemd/user
    cp resources/systemd/equity-engine-daily.* ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now equity-engine-daily.timer
    systemctl --user list-timers equity-engine-daily.timer      # next run
    journalctl --user -u equity-engine-daily.service -n 50      # last run's output

`loginctl enable-linger $USER` keeps user timers running when no session is open. Weekend special
sessions (Muhurat trading) are not covered by the Mon..Fri calendar; run `ingest.py daily` by hand.
