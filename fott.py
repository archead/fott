import sqlite3, os, subprocess, json, argparse, shutil
from datetime import datetime
from pathlib import Path

STREAM_TITLE = "Stereo (Boosted Dialogue)"
SUPPORTED_EXTENSIONS = [".mkv", ".mp4"]
ARCHIVE_FOLDER_NAME = "fott_archive"

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

    print("\n[Starting fott...]")

    working_directory = Path.cwd()
    file_list = os.listdir(working_directory)

    for file in file_list:
        
        file = Path(file)
        if file.suffix not in SUPPORTED_EXTENSIONS:
            print("[Warning]", file.name, "\nFile/Directory not supported, skipping...\n")
            continue

        print("\n[Current file]:", file)
       
        full_path = file.absolute()
        
        info = ffprobe_to_json(full_path)
        target_stream = check_for_candidates(info)

        output_file = Path(file)
        output_file = output_file.with_name(output_file.stem + "_converted.mkv")
        print("[Creating]:", output_file.name)

        stream_count = len(info["streams"])
        result = convert_to_stereo(full_path, target_stream, stream_count, STREAM_TITLE, output_file, args.dry)

        if (result):
            archive_file(file)
            if not args.dry and output_file.exists():
                output_file.rename(file.with_name(file.stem + ".mkv"))
            else:
                print("[Dry run] No file created")
        
        # placeholder for now
        sql = """
        INSERT INTO fott_media (source_path, source_name, coverted_name, converted_at)
        VALUES (?, ?, ?, ?)
        """

def convert_to_stereo(input: Path, target_stream: int, target_output_stream: int, stream_title: str, output: Path, dry_run: bool = False):
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

    result = subprocess.run(cmd, check=True)
    return result

def archive_file(src_file_path: Path):
    archive_folder = Path.cwd() / ARCHIVE_FOLDER_NAME
    archive_folder.mkdir(parents=True, exist_ok=True)
    
    dst = archive_folder / src_file_path.name
    shutil.move(src_file_path, dst)
    print("[Archived]:", src_file_path, "to", ARCHIVE_FOLDER_NAME)

def ffprobe_to_json(file_path: Path):
    cmd = [
            "ffprobe",
            "-v", "error",
            "-show_streams",
            "-select_streams", "a",
            "-print_format", "json",
            file_path
        ]
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(p.stdout)

def check_for_candidates(stream_info):
    streams = stream_info["streams"]
    stream_count = len(streams)
    target_stream = 0 # default stream if no other candidates exist

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

    return target_stream
    
if __name__ == "__main__":
    main()
