import sqlite3, os, subprocess, json, sys

STREAM_TITLE = "Stereo (Boosted Dialogue)"
SUPPORTED_EXTENSIONS = ["mkv", "mp4"]

working_directory = os.getcwd()
print(working_directory)

file_list = os.listdir(working_directory)

for file in file_list:
    if "." not in file:
        continue
    if file.rsplit(".", 1)[1] not in SUPPORTED_EXTENSIONS:
        continue

    full_path = os.path.join(working_directory, file)
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_streams",
        "-select_streams", "a",
        "-print_format", "json",
        full_path
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(p.stdout)

    streams = info["streams"]
    stream_count = len(streams)
    target_stream = 0

    print("Current file:", file)

    if (stream_count > 1):
        print("\nMultiple candidates detected, please choose target stream:\n")
        
        candidates = []

        for audio_index, s in enumerate(streams):
            if s.get("channels") < 6:
                continue

            tags = s.get("tags", {})
            stream_details = {
                "index": audio_index,
                "title": tags.get("title", "missing info"),
                "lang": tags.get("language", "missing info")
            }
            candidates.append(stream_details)
        
        valid_options = [o["index"] for o in candidates]
        while True:
            for candidate in candidates:
                print("Stream #[", candidate["index"], "] :",
                    "\nTitle: ", candidate["title"],
                        "\nLanguage: ", candidate["lang"], "\n-----------------",
                        sep="")

            print("Select Stream #", valid_options , ":")
            user_defined_target = int(input())

            if user_defined_target in valid_options:
                target_stream = user_defined_target
                break
            else:
                print("Please select valid Stream # []")

    output_file = file.rsplit(".", 1)[0] + ".mkv"
    print("Creating:", "converted_"+output_file)
    output_file = os.path.join(working_directory, "converted_"+output_file)
    
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error", "-stats",

        "-i", full_path,

        "-map", "0",
        "-map", f"0:a:{target_stream}", 

        "-c", "copy",

        f"-filter:a:{stream_count}", "pan=stereo|FL=1.2*FC+0.7*FL+0.7*BL|FR=1.2*FC+0.7*FR+0.7*BR",
        f"-c:a:{stream_count}", "aac",
        f"-b:a:{stream_count}", "192k",

        f"-metadata:s:a:{stream_count}", f"title={STREAM_TITLE}",
        output_file
    ]

    subprocess.run(cmd, check=True)
    
