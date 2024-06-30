import tkinter as tk
from tkinter import filedialog, Event
import yt_dlp
import csv
import threading
import googleapiclient.discovery
from googleapiclient.errors import HttpError
import requests
import math
import io

class Map:
    LINK = 3
    TITLE = 4
    CHANNEL = 5
    STATE = 7
    ALT_LINK = 8
    FOUND = 9
    NOTES = 10

csv_str: str = requests.get('https://docs.google.com/spreadsheets/d/1rEofPkliKppvttd8pEX8H6DtSljlfmQLdFR-SlyyX7E/export?format=csv').content.decode()
csv_reader = csv.reader(io.StringIO(csv_str))
archive_rows = [row for row in csv_reader]
del archive_rows[0]
total_videos = len(archive_rows)
videos_to_fetch = total_videos

# Initialize the yt-dlp downloader
ydl_opts = {
    'quiet': True,
    'max_threads': 4,  # Adjust the number of concurrent downloads
    'retries': 3,      # Number of retries for failed downloads
    'sleep_interval': 3,  # Time to wait between retries (in seconds)
}
ydl = yt_dlp.YoutubeDL(ydl_opts)

# Function to check non-YouTube video status
def check_non_youtube_video_status(ydl, video_url):
    try:
        info_dict = ydl.extract_info(video_url, download=False)
        if info_dict.get('upload_date', None):
            video_status = "Found"
            specific_status = info_dict.get('access_control', {}).get('form', 'Public')
            video_status += f": {specific_status}" if specific_status != "Public" else ": Public"
        else:
            video_status = "Missing: deleted or private"
        return video_status
    except yt_dlp.DownloadError as e:
        return f"Error: {str(e)}"

# Function to check video status using YouTube Data API
def check_youtube_video_status(video_id, youtube, tries=0):
    try:
        response = youtube.videos().list(
            part="snippet,contentDetails,status",
            id=video_id
        ).execute()

        if response.get("items"):
            item = response["items"][0]
            video_title = item["snippet"]["title"]
            status_info = item.get("status", {})
            privacy_status = status_info.get("privacyStatus", "public")
            age_restricted = item["contentDetails"].get("contentRating", {}).get("ytRating") == "ytAgeRestricted"

            blocked_countries = []
            video_details = item["contentDetails"]
            region_restriction = video_details.get("regionRestriction", {})
            blocked_countries = region_restriction.get("blocked", [])


            return video_title, status_to_str(privacy_status, blocked_countries, age_restricted), blocked_countries
        else:
            return "Video not found", "unavailable", []

    except HttpError as e:
        if e.resp.status == 404:
            return "Video not found", "Missing: deleted or private", []
        elif e.resp.status == 400 and tries < 3:
            return check_youtube_video_status(video_id, youtube, tries + 1)
        
        raise e

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

        # + 1 Since the video rows start at row 2
        starting_row_num = int(checks_row_start_entry.get()) + 1
        processed_videos = 0

        archive_rows = archive_rows[starting_row_num - 2 : int(checks_row_end_entry.get()) + 1]
        output_csv_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])

        updated_rows = []

        for i, archive_row in enumerate(archive_rows):
            video_url = archive_row[Map.LINK]
            video_title = archive_row[Map.TITLE]

            if "youtube.com" in video_url:
                video_id = video_url.split("v=")[-1]
                updated_video_title, video_status, blocked_countries = check_youtube_video_status(video_id, youtube)
                
                if updated_video_title == "Video not found":
                    updated_video_title = video_title

            else:
                video_status = check_non_youtube_video_status(ydl, video_url)
                blocked_countries = []
                # Todo: check for video title updates
                updated_video_title = video_title

            if video_title != updated_video_title:
                updated_rows.append(["Current", starting_row_num + i, video_url, video_title, archive_row[Map.STATE], ', '.join(blocked_countries) if 'blocked' in video_status.lower() else ''])
                updated_rows.append(["Updated", starting_row_num + i, video_url, updated_video_title, video_status, ', '.join(blocked_countries) if 'blocked' in video_status.lower() else ''])
                updated_rows.append([""] * len(updated_rows[-1]))

            # Update progress label on the main thread
            processed_videos += 1

            progress_label.config(text=f"Progress: {processed_videos}/{videos_to_fetch} videos checked")

        # Write to the output CSV with headers
        header = ["", "Archive Row", "Video URL", "Video Title", "Video Status", "Blocked Countries"]
        with open(output_csv_path, 'w', encoding='utf-8') as output_csvfile:
            csv_writer = csv.writer(output_csvfile, lineterminator="\n")
            csv_writer.writerow(header)
            csv_writer.writerows(updated_rows)

        # Update the result label on the main thread
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
            checks_row_start_entry.insert(0, 1)
            return

        clamped = max(1, min(start, end))

        if clamped != start:
            checks_row_start_entry.delete(0, int(math.log10(abs(start))) + 1 + (abs(start) != start))
            checks_row_start_entry.insert(0, clamped)

        videos_to_fetch = end - clamped + 1

    elif e.widget._name == "end":
        start = int(start)

        try:
            end = int(end)
        except:
            checks_row_end_entry.delete(0, len(end))
            checks_row_end_entry.insert(0, total_videos)
            return
        
        clamped = max(start, min(end, total_videos))

        if clamped != end:
            checks_row_end_entry.delete(0, int(math.log10(abs(end))) + 1 + (abs(end) != end))
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

checks_row_start_entry = tk.Entry(root, name="start",)
checks_row_start_entry.bind("<Return>", clamp_to_archive_range)
checks_row_start_entry.bind("<FocusOut>", clamp_to_archive_range)
checks_row_start_entry.insert(0, "1")
checks_row_start_entry.pack()

checks_row_end_entry = tk.Entry(root, name="end")
checks_row_end_entry.bind("<Return>", clamp_to_archive_range)
checks_row_end_entry.bind("<FocusOut>", clamp_to_archive_range)
checks_row_end_entry.insert(0, total_videos)

checks_row_end_entry.pack()

start_button = tk.Button(root, text="Run Status Checker", command=run_status_checker)
start_button.pack()

progress_label = tk.Label(root, text=f"Progress: 0/{total_videos} videos checked")
progress_label.pack(pady=10)

result_label = tk.Label(root, text="")
result_label.pack(pady=10)

root.mainloop()