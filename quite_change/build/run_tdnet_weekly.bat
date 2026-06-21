@echo off
REM Weekly forward-engine run: capture the last 8 days of 通期 決算短信 from the free TDnet site.
REM Registered as Windows Scheduled Task "QuietChange_TDnet_Weekly". Logs to _tdnet_db\_runlog.txt.
cd /d "c:\Users\Sahal Saeed\Documents\tempest_ai\quick\New_quick\new_quick\quite_change"
python build\collect_tdnet.py
