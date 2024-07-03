import tkinter as tk

from googleapiclient.errors import HttpError
from tkinter import filedialog, Event
from Enums import States, ArchiveIndices
from typing import List, Tuple

import googleapiclient.discovery
import yt_dlp
import csv
import threading
import requests
import math
import io


csv_str: str = requests.get('https://docs.google.com/spreadsheets/d/1rEofPkliKppvttd8pEX8H6DtSljlfmQLdFR-SlyyX7E/export?format=csv').content.decode()
# The requested archive csv comes with extra sets of quotes around titles that include
# quotation marks so a csv_reader is necessary to accomodate for that
csv_reader = csv.reader(io.StringIO(csv_str))
archive_rows = [row for row in csv_reader]
# -1 since the first row is a header
videos_to_fetch = len(archive_rows) - 1

ydl_opts = {
    'quiet': True,
    'retries': 3,
    'sleep_interval': 3,
}

ydl = yt_dlp.YoutubeDL(ydl_opts)

def check_non_youtube_video_status(ydl, video_url) -> Tuple[str, List[States]]:
    try:
        status = []

        info_dict = ydl.extract_info(video_url, download=False)

        if info_dict.get('upload_date', None):
            specific_status = info_dict.get('access_control', {}).get('form', 'Public')

            if specific_status != 'Public':
                # breakpoint
                status.append(States.get(specific_status))
        else:
            status.append(States.UNAVAILABLE)
        return 'title or smt idk TODO', status
    except yt_dlp.DownloadError as e:
        # Todo
        raise e

# Function to check video status using YouTube Data API
def check_youtube_video_status(video_id, youtube, tries=0) -> Tuple[str, List[States], List[str]]:
    try:
        response = youtube.videos().list(
            part="snippet,contentDetails,status",
            id=video_id
        ).execute()

        if response.get("items"):
            states = []

            item = response["items"][0]
            video_title = item["snippet"]["title"]
            status_info = item.get("status", {})
            video_details = item["contentDetails"]

            if not status_info.get("embeddable"):
                states.append(States.NON_EMBEDDABLE)
            
            if video_details.get("contentRating", {}).get("ytRating") == "ytAgeRestricted":
                states.append(States.AGE_RESTICTED)

            region_restriction = video_details.get("regionRestriction", {})

            blocked_countries = ["EVERYWHERE EXCEPT:"] + region_restriction.get("allowed") if "allowed" in region_restriction else region_restriction.get("blocked", [])
            if len(blocked_countries) >= 5 or "allowed" in region_restriction:
                states.append(States.BLOCKED)


            return video_title, states, blocked_countries #status_to_str(privacy_status, blocked_countries, age_restricted), blocked_countries
        else:
            return "Video not found", [States.UNAVAILABLE], []

    except HttpError as e:
        if e.resp.status == 404:
            return "Video not found", [States.UNAVAILABLE], []
        elif e.resp.status == 400 and tries < 3:
            return check_youtube_video_status(video_id, youtube, tries + 1)
        
        print(f"\033[91m\n{e.reason}")
        quit(1)

def status_to_str(privacy: str, blocked_countries: list, age_restricted: bool):
    video_status = f"Found: {privacy}"
            
    if len(blocked_countries) > 5:
        video_status += f", BLOCKED:{len(blocked_countries)}"

    if age_restricted:
        video_status += ", age-restricted"

    return video_status

# Function to check video status and generate the result CSV
def run_status_checker():
    if not youtube_api_key_entry.get().strip(): return

    youtube_api_key = youtube_api_key_entry.get().strip()  # Get the YouTube Data API key from the entry field

    def check_videos():
        global archive_rows

        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=youtube_api_key)

        starting_row_num = int(checks_row_start_entry.get())
        processed_videos = 0

        checking_range = archive_rows[starting_row_num - 1 : int(checks_row_end_entry.get())]
        output_csv_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])

        if not output_csv_path: return

        updated_rows = []

        for i, archive_row in enumerate(checking_range):
            archive_row_states = archive_row[ArchiveIndices.STATE].split('/') if len(archive_row[ArchiveIndices.STATE].split('/')) != 1 else archive_row[ArchiveIndices.STATE].split(' & ')
            archive_row_states = [States.get(state) for state in archive_row_states if States.get(state) != None]

            video_url = archive_row[ArchiveIndices.LINK]
            video_title = archive_row[ArchiveIndices.TITLE]

            if "youtube.com" in video_url:
                video_id = video_url.split("v=")[-1]
                updated_video_title, video_states, blocked_countries = check_youtube_video_status(video_id, youtube)
                
                if updated_video_title == "Video not found":
                    updated_video_title = video_title

            else:
                updated_video_title, video_states = check_non_youtube_video_status(ydl, video_url)
                blocked_countries = []
                # Todo: check for video title updates
                updated_video_title = video_title

            if (
                (check_titles_var.get() and (video_title != updated_video_title)) or
                (len(blocked_countries) >= 5 and States.BLOCKED not in archive_row_states) or
                (len(blocked_countries) < 5 and States.BLOCKED in archive_row_states and "EVERYWHERE EXCEPT:" not in blocked_countries) or
                (any(video_state not in archive_row_states for video_state in video_states)) or
                (any(archive_state not in video_states for archive_state in archive_row_states))
            ):
                updated_rows.append(["Current", starting_row_num + i, video_url, video_title, archive_row[ArchiveIndices.STATE], ', '.join(blocked_countries) if States.BLOCKED in archive_row_states else ''])
                updated_rows.append(["Updated", starting_row_num + i, video_url, updated_video_title, ' & '.join(map(lambda state: state.value[0], tuple(video_states))) if video_states else '', ', '.join(blocked_countries) if States.BLOCKED in video_states else ''])
                updated_rows.append([""] * len(updated_rows[-1]))

            processed_videos += 1
            progress_label.config(text=f"Progress: {processed_videos}/{videos_to_fetch} videos checked")

        # Write to the output CSV with headers
        header = ["", "Archive Row", "Video URL", "Video Title", "Video Status", "Blocked Countries"]
        with open(output_csv_path, 'w', encoding='utf-8') as output_csvfile:
            csv_writer = csv.writer(output_csvfile, lineterminator="\n")
            csv_writer.writerow(header)
            csv_writer.writerows(updated_rows)

        result_label.config(text=f"Output CSV saved at: {output_csv_path}")

    # Run the check_videos function in a separate thread
    threading.Thread(target=check_videos).start()

def clamp_to_archive_range(e: Event):
    global videos_to_fetch
    start = checks_row_start_entry.get()
    end = checks_row_end_entry.get()

    if e.widget._name == "start":
        end = int(end)

        try:
            start = int(start)
        except:
            checks_row_start_entry.delete(0, len(start))
            checks_row_start_entry.insert(0, 2)
            videos_to_fetch = end - 1
            progress_label.config(text=f"Progress: 0/{videos_to_fetch} videos checked")
            return

        clamped = max(2, min(start, end))

        if clamped != start:
            checks_row_start_entry.delete(
                0,
                int(math.log10(abs(start))) + 1 + (abs(start) != start) if start != 0 else 2
            )
            checks_row_start_entry.insert(0, clamped)

        videos_to_fetch = end - clamped + 1

    elif e.widget._name == "end":
        start = int(start)

        try:
            end = int(end)
        except:
            checks_row_end_entry.delete(0, len(end))
            checks_row_end_entry.insert(0, len(archive_rows))
            videos_to_fetch = len(archive_rows) - start + 1
            progress_label.config(text=f"Progress: 0/{videos_to_fetch} videos checked")
            return
        
        clamped = max(start, min(end, len(archive_rows)))

        if clamped != end:
            checks_row_end_entry.delete(
                0,
                int(math.log10(abs(end))) + 1 + (abs(end) != end) if end != 0 else 2
            )
            checks_row_end_entry.insert(0, clamped)

        videos_to_fetch = clamped - start + 1
    
    progress_label.config(text=f"Progress: 0/{videos_to_fetch} videos checked")



# Create the main GUI window
root = tk.Tk()
root.title("YouTube Video Status Checker")

youtube_api_key_label = tk.Label(root, text="Enter YouTube Data API Key:")
youtube_api_key_label.pack()
youtube_api_key_entry = tk.Entry(root, show="*")
youtube_api_key_entry.pack()



range_frame = tk.Frame(root)
range_frame.pack(pady=5)

range_label = tk.Label(range_frame, text="Range")
range_label.pack(pady=(0, 3))

checks_row_start_entry = tk.Entry(range_frame, name="start", width=10)
checks_row_start_entry.bind("<Return>", clamp_to_archive_range)
checks_row_start_entry.bind("<FocusOut>", clamp_to_archive_range)
checks_row_start_entry.insert(0, 2)
checks_row_start_entry.pack(side="left", padx=5)

checks_row_end_entry = tk.Entry(range_frame, name="end", width=10)
checks_row_end_entry.bind("<Return>", clamp_to_archive_range)
checks_row_end_entry.bind("<FocusOut>", clamp_to_archive_range)
checks_row_end_entry.insert(0, len(archive_rows))
checks_row_end_entry.pack(side="left", padx=5)



options_frame = tk.Frame(root)
options_frame.pack(pady=8)

options_label = tk.Label(options_frame, text="Options")
options_label.grid(row=0, column=0, sticky=tk.W)

check_titles_var = tk.BooleanVar()
check_titles = tk.Checkbutton(options_frame, text="Check Title Differences", variable=check_titles_var)
check_titles.grid(row=1, column=0)



run_frame = tk.Frame(root)
run_frame.pack(pady=(15, 5))

start_button = tk.Button(run_frame, text="Run Status Checker", command=run_status_checker)
start_button.pack()

progress_label = tk.Label(run_frame, text=f"Progress: 0/{videos_to_fetch} videos checked")
progress_label.pack(pady=3)



result_label = tk.Label(root, text="")
result_label.pack(pady=10)

root.mainloop()