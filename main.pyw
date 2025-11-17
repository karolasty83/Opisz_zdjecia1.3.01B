# -*- coding: utf-8 -*-
import wx
from core import (
    ensure_config,
    ensure_valid_working_folder_or_exit,
    ensure_prompts_file_on_start,
    prompt_for_api_if_missing,
)
from ui import StartFrame

def main():
    app = wx.App(False)  # <-- PRZENIEŚ NA POCZĄTEK

    _, config_created = ensure_config()
    ensure_prompts_file_on_start()          # bez MessageBox (patrz pkt 2)
    ensure_valid_working_folder_or_exit()   # nie tworzy własnego App

    if config_created:
        prompt_for_api_if_missing()         # nie tworzy własnego App

    start = StartFrame()
    start.Show()
    app.MainLoop()

if __name__ == "__main__":
    main()
