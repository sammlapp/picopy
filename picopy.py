from math import ceil
import datetime

print(f"started picopy at {datetime.datetime.now()}")
from gpiozero import LED, Button
from time import sleep, time
import os
from glob import glob
from shutil import disk_usage
import shlex
import subprocess
import threading
from pathlib import Path
import queue

# GPIO pin setup for LEDs and Buttons
status_led = LED(18)
progress_led = LED(27)
error_led = LED(22)
src_mounted_led = LED(23)
dest_mounted_led = LED(24)

go_button = Button(4, hold_time=1)
cancel_button = Button(17, hold_time=1)
eject_button = Button(5, hold_time=1)
# power button is GPIO3, but managed by a separate script

# script parameters
mount_check_interval = 1  # every x seconds, check if a source and destination are mounted
mount_location = "/media/pi"  # location of mounted USB devices
ui_sleep_time = 0.05  # seconds to sleep between checking for user input
min_file_size = "100k"  # minimum .wav/.WAV file size to include: 100kb ~=1sec .WAV audio
# note: all files other than .wav and .WAV are copied regardless of size, but 
# except the excluded file types: '.Trashes'  '.fsevents*' 'System*' '.Spotlight*'

# initialize global variables
rsync_process = None
rsync_outq = None
rsync_thread = None
dest_save_dir = None


def log(s):
    print(f"{datetime.datetime.now()} [{status}]:\t{s}")


def output_parser(process):
    """read output from Popen STDOUT"""
    out = []
    for line in iter(process.stdout.readline, b""):
        out.append(line.decode("utf-8"))
    return out


def output_reader(process, outq):
    """send output from Popen STDOUT to a queue"""
    for line in iter(process.stdout.readline, b""):
        outq.put(line.decode("utf-8"))


def update_leds(status):
    """update status, progress, and error leds to reflect the current status"""
    # status LED
    if status == "copying":
        status_led.blink(0.25, 0.25, n=None, background=True)
    elif status == "idle":
        status_led.blink(0.1, 2.9, n=None, background=True)
    elif status == "ready_to_copy":
        status_led.blink(1, 1, n=None, background=True)
    elif status == "complete_transfer":
        status_led.on()
    else:
        status_led.off()

    # error LED
    if status == "incomplete_transfer":
        error_led.on()
    else:
        error_led.off()

    # progress LED
    if status == "complete_transfer":
        progress_led.on()
    elif status != "copying":
        progress_led.off()


def get_free_space(disk, scale=2 ** 30):
    return float(disk_usage(disk).free) / scale


def get_used_space(disk, scale=2 ** 30):
    return float(disk_usage(disk).used) / scale


def blink_error(n, reps=2):
    """blink the error led to send a message"""
    for r in range(reps):
        for i in range(n):
            error_led.on()
            sleep(0.2)
            error_led.off()
            sleep(0.2)
        sleep(0.4)


def blink_progress_led(outof10):
    """blink the progress led up to 10 times to indicate progress out of 10"""
    if outof10 > 10 or outof10 < 0:
        raise ValueError(f"outof10 must be int in 0-10. got {outof10}")
    progress_led.blink(0.1, 0.15, outof10)
    sleep(3 - 0.25 * outof10)


def get_src_drive():  # TODO: blink the drive LED rather than error
    """search for source and destination drives mounted at mount_location
    a source drive does is any drive listed in /media/pi/ that does not have a file/folder named PICOPY_DESTINATION in root directory
    must find exactly one. if zero returns None, if >1 blinks error"""
    drives = glob(f"{mount_location}/*")
    src_drives = []
    for d in drives:
        if not os.path.exists(f"{d}/PICOPY_DESTINATION"):
            src_drives.append(d)
    if len(src_drives) > 1:
        log("ERR: found multiple source drives")
        blink_error(3, 2)
        return None
    elif len(src_drives) < 1:
        return None
    return src_drives[0]


def get_dest_drive():
    # a destination drive has file/folder PICOPY_DESTINATION in root directory
    # must find exactly one. if zero returns None, if >1 blinks error
    drives = glob(f"{mount_location}/*")
    dest_drives = []
    for d in drives:
        # log(f'checking for {d}/PICOPY_DESTINATION')
        if os.path.exists(f"{d}/PICOPY_DESTINATION"):
            dest_drives.append(d)
    if len(dest_drives) > 1:
        log("ERR: found multiple destination drives")
        blink_error(4, 2)
        return None
    elif len(dest_drives) < 1:
        return None
    return dest_drives[0]


def eject_drive(source=True):
    """eject the source drive (source=True) or dest drive (source=False)"""
    log("attempting to eject")

    drive = get_src_drive() if source else get_dest_drive()
    log(drive)

    if drive is None:
        log("ERR: no drive to eject")
    else:
        # try to eject the disk with system eject command
        cmd = f"eject {drive}"
        log(cmd)
        response = subprocess.Popen(
            shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        # response.communicate()
        [log(r) for r in output_parser(response)]

    sleep(1)


def prepare_copy():
    log("checking for source and dest drives")

    source = get_src_drive()
    if source is None:
        blink_error(3, 3)
        log("ERR: no source found")
        return "idle", None, None

    dest = get_dest_drive()
    if dest is None:
        blink_error(4, 3)
        log("ERR: no destination found. Dest should contain file or folder PICOPY_DESTINATION in root")
        return "idle", None, None

    log(f"found source drive {source} and destination drive {dest}")

    # ok, now we know we have 1 source and 1 destination
    # check that enough space on the dest for source
    log("checking free space")
    src_size = get_used_space(source)
    dest_free = get_free_space(dest)
    log(f"\tsrc size: {src_size} Gb")
    log(f"\tdest free: {dest_free} Gb")
    if src_size > dest_free:
        log("ERR: not enough space on dest for source")
        blink_error(5, 2)  # raise NotEnoughSpaceError
        return "idle", source, dest

    # if we make it to hear, we are ready to copy
    # there is a source and a destination with enough space for it
    return "ready_to_copy", source, dest


def start_progress_monitor_thread(source, dest, rsync_thread):
    progress_q = queue.Queue()

    progress_monitor_thread = threading.Thread(
        target=monitor_progress, args=(source, dest, progress_q, rsync_thread)
    )
    progress_monitor_thread.start()
    return progress_monitor_thread, progress_q


def monitor_progress(source, dest, progress_q, rsync_thread):
    src_size = get_used_space(source)
    dest_free = get_free_space(dest)
    while rsync_thread.is_alive():
        sleep(6)
        copied_size = dest_free - get_free_space(dest)
        progress_float = copied_size / src_size
        progress_q.put(progress_float)


def start_copy_thread(source, dest):

    log("copying")
    sleep(0.5)
    time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_save_dir = dest + "/" + os.path.basename(source) + "_" + time_str

    # first create the directory
    Path(dest_save_dir).mkdir(exist_ok=True, parents=True)

    # we will run two rsync commands, copying all non-wav files then including wav files over min_file_size
    # first copy everything except .wav, .WAV, and architve files we don't want
    cmd = (
        f"rsync -rv --log-file=./rsync.log --progress " +
        f"--exclude .Trashes --exclude '.fsevents*' --exclude 'System*' --exclude '.Spotlight*' " +
        f"--exclude '*.wav' --exclude '*.WAV' {source} {dest_save_dir}"
        )
    log(cmd)
    subprocess.run(shlex.split(cmd))
    
    # second, copy .wav and .WAV files above min_file_size
    cmd = (
        f"rsync -rv --log-file=./rsync.log --min-size={min_file_size} --progress --ignore-existing " +
        f"--exclude .Trashes --exclude '.fsevents*' --exclude 'System*' --exclude '.Spotlight*' " +
        f"{source} {dest_save_dir}"
        )
    log(cmd)
    rsync_process = subprocess.Popen(
        shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )

    # start a thread to watch the rsync process and catch output
    rsync_outq = queue.Queue()

    rsync_thread = threading.Thread(
        target=output_reader, args=(rsync_process, rsync_outq)
    )
    rsync_thread.start()

    # return the queue, thread, and process
    # we can read the queue and terminate the process from outside this function
    return ("copying", rsync_process, rsync_outq, rsync_thread, dest_save_dir)


def check_dest_synced(source, dest, dest_save_dir):
    log("checking if dest has all files from source")
    start_time = time()

    n_files_out_of_sync = 0

    # check sync of non wav/WAV files: (dry run with -n flag and --stats)
    cmd = (
        f"rsync -rvn --stats  --progress " +
        f"--exclude .Trashes --exclude '.fsevents*' --exclude 'System*' --exclude '.Spotlight*' " +
        f"--exclude '*.wav' --exclude '*.WAV' {source} {dest_save_dir}"
        )
    log(cmd)
    check_process = subprocess.Popen(
        shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    return_values = [
        f
        for f in output_parser(check_process)
        if "Number of regular files transferred" in f
    ]
    log(return_values)
    n_files_out_of_sync += int(return_values[0].split(" ")[-1])

    # check sync of all wav/WAV files over size limit:
    # rsync command (dry run) to see if any files would be transferred based on size difference
    cmd = (
        f"rsync -rvn --stats --min-size={min_file_size} --progress --ignore-existing " +
        f"--exclude .Trashes --exclude '.fsevents*' --exclude 'System*' --exclude '.Spotlight*' " +
        f"{source} {dest_save_dir}"
        )
    log(cmd)
    check_process = subprocess.Popen(
        shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    # check_process.communicate()
    return_values = [
        f
        for f in output_parser(check_process)
        if "Number of regular files transferred" in f
    ]
    log(return_values)

    n_files_out_of_sync += int(return_values[0].split(" ")[-1])
    log(n_files_out_of_sync)
    return n_files_out_of_sync == 0


def cancel_button_held():
    log("cancel button held")
    sleep(1)  # so that we don't repeat quickly
    if not status in ("copying", "incomplete_copy", "complete_copy"):
        # whatever status we were in, return to idle status
        return "idle"
    elif status != "copying":  # no action
        return status

    # if we get here, status is "copying". we want to cancel the copy.
    if rsync_process is None:
        # if status is copying, but no rsync process, return to idle status
        return "idle"

    # if status is copying and rsync process is running, cancel it
    rsync_process.terminate()
    try:
        rsync_process.wait(timeout=5)
        log(f"== subprocess rsync_process exited with rx={rsync_process.returncode}")
    except subprocess.TimeoutExpired:
        log("subprocess rsync_process did not terminate in time")

    # because the transfer was cancelled, we go to "incomplete_transfer"
    return "incomplete_transfer"


# the main loop only catches user input and sends work to threads
status = "idle"
log("status: " + status)

# TODO: leds for mounted source and dest drives (update every few seconds)
last_mount_check = -1
prev_status = None
while True:

    sleep(ui_sleep_time)

    # handle user input
    if cancel_button.is_held:
        status = cancel_button_held()
        sleep(3)
    elif go_button.is_pressed and status == "idle":
        log("go button pressed")
        status, source, dest = prepare_copy()
        sleep(1)
    elif go_button.is_pressed and status == "complete_transfer":
        log("user aknowledged finished transfer")
        status = "idle"
        sleep(1)
    elif go_button.is_held and status == "incomplete_transfer":
        # requires user to HOLD go button to aknowledge an incomplete transfer
        log("user akcnowledged incomplete transfer")
        status = "idle"
        sleep(3)
    elif go_button.is_pressed and status == "ready_to_copy":
        # start copy thread
        status, rsync_process, rsync_outq, rsync_thread, dest_save_dir = start_copy_thread(
            source, dest
        )
        progress_monitor_thread, progress_q = start_progress_monitor_thread(
            source, dest, rsync_thread
        )
        sleep(1)
    elif eject_button.is_pressed:
        if status == "ready_to_copy":
            status = "idle"
        # wait to see if this is a simple press or hold:
        eject_button.wait_for_release(1)
        if eject_button.is_held:
            # eject the destination drive
            log("ejecting destination")
            eject_drive(source=False)
            sleep(3)
        else:  # short press, no longer held
            # eject the source drive
            log("ejecting source")
            eject_drive(source=True)
            sleep(1)

    # handle end-of-copy: check integrity of copy
    if status == "copying" and not rsync_thread.is_alive():
        # we are done copying, or it failed
        log("rsync thread finished")
        status = "check_transfer"

        status_led.blink(0.25, 0.25)
        sleep(0.25)
        progress_led.blink(0.25, 0.25)

        # report finished or incomplete transfer
        complete_transfer = check_dest_synced(source, dest, dest_save_dir)
        if complete_transfer:
            log("transfer was complete. Press Go to acknowledge.")
            status = "complete_transfer"
        else:
            log("ERR: transfer was not complete. Hold Go to acknowledge.")
            status = "incomplete_transfer"
        status_led.off
        progress_led.off

    # check if source and dest drives are mounted
    if time() - last_mount_check > mount_check_interval:
        last_mount_check = time()
        src_mounted_led.off() if get_src_drive() is None else src_mounted_led.on()
        dest_mounted_led.off() if get_dest_drive() is None else dest_mounted_led.on()

    # check if status changed during this iteration
    status_changed = status != prev_status
    if status_changed:
        log(f"status: {status}")

    # update LEDs and depending on status:
    if status_changed:
        update_leds(status)

    # read output of copying thread to the log
    if status == "copying":
        # read lines from rsync output
        try:
            line = rsync_outq.get(block=False)
            log(line)
        except queue.Empty:
            pass  # no lines in queue

        # update status LED using messages from progress_q
        try:
            progress_float = progress_q.get(block=False)
            progress_outof10 = ceil(progress_float * 10)
            blink_progress_led(progress_outof10)
        except queue.Empty:
            pass

    prev_status = status
