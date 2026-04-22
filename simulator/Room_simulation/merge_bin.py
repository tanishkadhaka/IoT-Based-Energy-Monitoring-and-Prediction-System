Import("env")

def post_prog_action(source, target, env):
    build_dir = env.subst("$BUILD_DIR")
    progname = env.subst("$PROGNAME")
    
    cmd = [
        env.subst("$PYTHONEXE"),
        "-m", "esptool",
        "--chip", "esp32",
        "merge_bin",
        "-o", f"{build_dir}/merged.bin",
        "--flash_mode", "dio",
        "--flash_freq", "40m",
        "--flash_size", "4MB",
        "0x1000", f"{build_dir}/bootloader.bin",
        "0x8000", f"{build_dir}/partitions.bin",
        "0x10000", f"{build_dir}/{progname}.bin"
    ]
    
    print("Generating merged.bin...")
    env.Execute(" ".join(cmd))

env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", post_prog_action)
