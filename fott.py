import sqlite3, os, subprocess, json, sys, argparse
from datetime import datetime

STREAM_TITLE = "Stereo (Boosted Dialogue)"
SUPPORTED_EXTENSIONS = ["mkv", "mp4"]
def main():

    connection = sqlite3.connect("fott.db")
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fott_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        
        source_path     TEXT NOT NULL UNIQUE,
        source_name     TEXT NOT NULL,
        coverted_name   TEXT NOT NULL,
        converted_at    TEXT NOT NULL
    );
    """)
    connection.commit()

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", help="Perform a dry run", action="store_true")
    args = parser.parse_args()

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

        print("\n[Current file]:", file)

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
                    print(
                        "Stream #[", candidate["index"], "] :",
                        "\nTitle: ", candidate["title"],
                        "\nLanguage: ", candidate["lang"], "\n",
                        sep=""
                    )

                input_str = "Select Stream #"+ str(valid_options) + ":"
                user_defined_target = int(input(input_str))

                if user_defined_target in valid_options:
                    target_stream = user_defined_target
                    break
                else:
                    print("Please select valid Stream # []")

        output_file = file.rsplit(".", 1)[0] + ".mkv"
        output_file = "converted_"+output_file
        print("[Creating]:", output_file)
        output_file = os.path.join(working_directory, "converted_"+output_file)

        convert_to_stereo(full_path, target_stream, stream_count, STREAM_TITLE, output_file, args.dry)

        
        sql = """
        INSERT INTO fott_media (source_path, source_name, coverted_name, converted_at)
        VALUES (?, ?, ?, ?)
        """

        cursor.execute(sql, (
            full_path,
            file,
            output_file,
            datetime.now().isoformat(timespec="seconds"),
        ))

        connection.commit()
        
    

def convert_to_stereo(input: str, target_stream: int, target_output_stream: int, stream_title: str, output: str, dry_run: bool = False):
    if not dry_run:
        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error", "-stats",

            "-i", input,

            "-map", "0",
            "-map", f"0:a:{target_stream}", 

            "-c", "copy",

            f"-filter:a:{target_output_stream}", "pan=stereo|FL=1.2*FC+0.7*FL+0.7*BL|FR=1.2*FC+0.7*FR+0.7*BR",
            f"-c:a:{target_output_stream}", "aac",
            f"-b:a:{target_output_stream}", "192k",

            f"-metadata:s:a:{target_output_stream}", f"title={stream_title}",
            output
        ]
    else:
        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error", "-stats",
            "-i", input,
            "-map", "0",
            "-map", f"0:a:{target_stream}", 
            "-c", "copy",
            "-f", "null", "-"
        ]

    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()
