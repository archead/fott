import sqlite3, os, subprocess, json, argparse, shutil, tomllib, tomli_w
from pathlib import Path
from importlib.resources import files

STREAM_TITLE = "Stereo (Boosted Dialogue)"
SUPPORTED_EXTENSIONS = [".mkv", ".mp4"]
ARCHIVE_FOLDER_NAME = "fott_archive"

def main():
    print("\n[Starting fott...]")

    args = init_args()
    config = load_config()
    dbcon = init_db(Path(config["database"]["path"]))

    working_directory = Path.cwd() if args.target_dir == "" else Path(args.target_dir)

    if args.set_config:
        set_config_path(config, args.set_config)
        return

    if args.config:
        config_path = Path(config["config"].get("path"))
        show_config(Path(config_path))
        return

    if args.scan: scan_directory(dbcon, working_directory)

    if not args.scan: convert_directory(dbcon, working_directory, args)

def show_config(config_path: Path):
    print("[Current Config]:\n")
    with open(config_path, "r") as f:
        print(f.read())

def load_config():
    data = (files("fott") / "config.toml").read_text()
    template_config = tomllib.loads(data)

    config_path = Path(os.path.expandvars(template_config.get("config").get("path")))

    # Check if base config already exists if not create it
    if not config_path.is_file():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.touch()
        with open(config_path, "w") as f:
            f.write(data)

    # Open the base config
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # Expand environment variables i.e. %appdata%
    config["database"]["path"] = os.path.expandvars(config["database"].get("path"))
    config["config"]["path"] = os.path.expandvars(config["config"].get("path"))

    current_config_path = Path(config["config"]["path"])

    # Check if the current config path in the base config is different from the template one, if so, load that instead
    if current_config_path != config_path:
        with open(current_config_path, "rb") as f:
            config = tomllib.load(f)

    config["database"]["path"] = os.path.expandvars(config["database"].get("path"))
    config["config"]["path"] = os.path.expandvars(config["config"].get("path"))

    return config

def set_config_path(config, config_path: Path):
    config["config"]["path"] = config_path

    data = (files("fott") / "config.toml").read_text()
    template_config = tomllib.loads(data)
    base_config_path = Path(os.path.expandvars(template_config["config"]["path"]))

    base_config_path.write_text(tomli_w.dumps(config), encoding="utf-8")

    print("[Config Path Set]:", config_path)

def scan_directory(dbcon, working_directory: Path):

    file_list = os.listdir(working_directory) if working_directory.is_dir() else [working_directory]

    current_file_counter = 0
    for src_file in file_list:
        current_file_counter += 1
        src_file = working_directory / src_file

        print("\n[Current File]:", src_file.name)
        if not supported_format(src_file): continue
        if previously_converted(dbcon, src_file): continue

        streams = ffprobe_to_json(src_file).get("streams")
        for s in streams:
            if s.get("tags").get("title") == STREAM_TITLE:
                print("[Stream Found]: Added to database\n")
                mark_done(dbcon, src_file)

def supported_format(src_file: Path) -> bool:
    if src_file.suffix not in SUPPORTED_EXTENSIONS:
        print("[Warning]:", src_file.name, "File/Directory not supported, skipping...\n")
        return False
    return True

def convert_directory(dbcon, working_directory: Path, args: argparse.Namespace):

    file_list = os.listdir(working_directory) if working_directory.is_dir() else [working_directory]

    current_file_counter = 0
    for src_file in file_list:
        current_file_counter += 1
        src_file = working_directory / src_file
        if not supported_format(src_file): continue

        print(f"\n[{current_file_counter}/{len(file_list)}]")
        print("[Current file]:\n\t", src_file)

        if previously_converted(dbcon, src_file, args.force):
            continue

        full_path = src_file.absolute()

        info = ffprobe_to_json(full_path)
        target_stream = check_for_candidates(info)

        output_file = Path(src_file)
        output_file = output_file.with_name(output_file.stem + "_converted.mkv")
        print("[Creating]:\n\t", output_file.name)

        stream_count = len(info["streams"])
        result = convert_to_stereo(full_path, target_stream, stream_count, STREAM_TITLE, output_file, args.dry)

        if result:
            archive_file(src_file)
            if not args.dry and output_file.exists():
                output_file = output_file.rename(src_file.with_name(src_file.stem + ".mkv"))
                mark_done(dbcon, output_file, src_file)
            else:
                print("[Dry run] No file created")

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
    archive_folder = src_file_path.parent / ARCHIVE_FOLDER_NAME
    archive_folder.mkdir(parents=True, exist_ok=True)
    
    dst = archive_folder / src_file_path.name
    shutil.move(src_file_path, dst)
    print("[Archived]:\n\t", src_file_path, "to", ARCHIVE_FOLDER_NAME)

def ffprobe_to_json(file_path: Path):
    cmd = [
            "ffprobe",
            "-v", "error",
            "-show_streams",
            "-select_streams", "a",
            "-print_format", "json",
            file_path
        ]
    p = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
    return json.loads(p.stdout)

def check_for_candidates(stream_info):
    streams = stream_info["streams"]
    stream_count = len([s for s in streams if s.get("channels") == 6])

    target_stream = 0 # default stream if no other candidates exist

    if stream_count > 1:
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

def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print("[Loaded Database]:", db_path)

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fott (
        id INTEGER PRIMARY KEY,
        src_path TEXT,
        out_path TEXT,
        out_size INTEGER,
        out_mtime_ns INTEGER,
        converted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (out_path, out_size, out_mtime_ns)
    );
    """)
    connection.commit()
    return connection

def previously_converted(dbcon, out_path: Path, force_convert: bool = False) -> bool:
    if force_convert:
        print("[Forced Conversion Enabled]")
        return False
    stats = out_path.stat()
    params = (str(out_path), stats.st_size, stats.st_mtime_ns)
    res = dbcon.execute( "SELECT converted_at FROM fott WHERE out_path=? AND out_size=? AND out_mtime_ns=?", params )
    rows = res.fetchall()

    if rows:
        print("[Warning]: File previously converted, skipping...")

        for (converted_at,) in rows:
            print("\tConversion Timestamp:", converted_at)
            print("\tUse [-f] or [--force] to overwrite this!")

        return True

    return False

def mark_done(dbcon,  out_path: Path, src_path: Path = None):
    stats = out_path.stat()
    dbcon.execute(
        "INSERT OR REPLACE INTO fott (src_path, out_path, out_size, out_mtime_ns) VALUES (?, ?, ?, ?)",
        (str(src_path), str(out_path), stats.st_size, stats.st_mtime_ns)
    )
    dbcon.commit()

def init_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_dir", help="Target directory or file, defaults to current", type=str, default="", nargs="?")
    parser.add_argument("-d", "--dry", help="Perform a dry run", action="store_true", default=False)
    parser.add_argument("-s", "--scan", help="Scan directory for previously converted files and add them to the database", action="store_true", default=False)
    parser.add_argument("-f", "--force", help="Overwrite existing conversions", action="store_true", default=False)
    parser.add_argument("--auto-delete", help="Auto delete original file after conversion", action="store_true", default=False)
    parser.add_argument("--config", help="Display current config and it's path", action="store_true", default=False)
    parser.add_argument("--set-config", help="Set config path", type=str, default=None)

    return parser.parse_args()

if __name__ == "__main__":
    main()
