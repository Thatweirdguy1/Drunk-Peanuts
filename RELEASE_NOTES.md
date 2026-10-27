## Drunk Peanuts 0.27.0

Play now supports **Play with Drunk Peanuts Play** and **Add to Drunk Peanuts Play playlist** on Windows folders (right-click → Show more options). Folder scans include supported media in subfolders and run in the background.

Enqueue requests append to the existing Play window without restarting the current track. The playlist toolbar supports adding files/folders, opening and saving M3U/M3U8 playlists, drag reordering, moving tracks up/down, removing selected entries and clearing the queue. Removing playlist entries never deletes media files. Play starts an idle queue; double-click selects a track. Existing next/previous, automatic advance and single-track repeat follow the edited queue.

The installer preserves existing default apps and VLC commands. For an older installation, use **Start → Drunk Peanuts → Repair Open with registration**. This adds classic folder context-menu actions, not a Windows 11 top-level shell extension.

Saved playlists reference local media; moving those files can break references. Remote streams, XSPF/PLS and automatic session recovery are outside this batch. See the [playlist report](https://github.com/Thatweirdguy1/Drunk-Peanuts/blob/main/docs/PLAYLISTS_027.md) for the VLC investigation and limits.

### Downloads
- DrunkPeanuts-0.27.0-Setup.exe — Windows Desktop/Start menu installer.
- DrunkPeanuts-Windows-x64.zip — extract the entire portable folder.
- DrunkPeanuts-macOS-Apple-Silicon.zip and DrunkPeanuts-macOS-Intel.zip.
- SHA256SUMS.txt — checksums.

Windows builds remain unsigned; macOS builds are not notarized. Full Office parity remains in progress.
