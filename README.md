# voc_detection_system

<p align="center">
  <img width="256" src="CAD_files/laser_cutter/COATL-2.pdf" />
</p>
<h2 align="center">CO4TL Lab Environmental Chamber</h4>

***lab logo here***

## System Overview:

This system is made up of three main parts:
- The Pi: which controls the mechanical systems
- The Microcontrollers, which logs sensor data from inside the chambers and sends it back to the pi for further logging processing
- TThe Machine learning model for post processing data

***stylized image of system here***

***image of physical system here***


<details>
<summary class="hint section_header">

## Setting up the Raspberry Pi $\color{gray}(click \space to \space expand)$
</summary>

> [!NOTE]
> It is recommended highly recommended that you install <u>Pi OS</u> over other OS options. Some modules, [LEDBreather](raspberry_pi_src\src\pi_src\control_sys\LEDBreather.py) in particular, may not work otherwise.

> [!TIP]
> It is recommended to use a spare check out of the "raspberry_pi_src" folder on the raspberry pi. Doing so avoids copying several files and requirements not used on the raspberry pi.

<details>
 <summary class="sub_header"> 
 
 ### How to sparse check out $\color{gray}(click \space to \space expand)$ 
 </summary>

<!-- ### How to sparse check out: -->
> **1.)** Initialize an empty clone (no files checked out yet):
> ```bash
> git clone --no-checkout https://github.com/jvandag/voc_detection_system
> cd voc_detection_system
> ```
> 
> **2.)** Enable sparse‑checkout in "cone" mode:
> ```bash
> git sparse-checkout init --cone
> ```
> Cone mode lets you specify whole directories without complex patterns. 
> 
> **3.)** Select the folder you care about (e.g. path/to/folder). If you cloned you're cloning to your home directory, > like recommended, this would be `voc_detection_system/raspberry_pi_src`:
> ```bash
> git sparse-checkout set raspberry_pi_src
> ```
> Now your working tree will contain only that folder (and the usual .git/). 
> 
> **4.)** Switch to the branch you want (likely main in this case):
> ```bash
> git checkout main
> ```
> You’ll see only `path/to/folder/` on disk, but Git still knows the full history. 
> 
> **Pulling:** `git pull` will fetch updates for the entire repo, but only update your sparse‑checked‑out folder in the > working tree.
> 
> **Pushing:** `git push` will only send the commits you’ve made (which affect only the sparse‑checked‑out folder) back > to origin. You won’t inadvertently delete or modify other directories because you never checked them out or staged > changes for them. 
> 
> <hr>
> </details>

### Initializing Raspberry Pi
Once you've cloned the repo to the pi, you can initialize the project by navigating to the repo and running the following commands

> [!IMPORTANT]
> Python version 3.9 or higher is required to ensure all scripts run correctly

```bash
cd raspberry_pi_src/src/pi_src/shell_scripts
./pi_first_time_setup.sh
```
This will install necessary dependancies, configure user permissions, setup your python venv, and install the necessary python libraries. It will also configure a cron job that will run a start up shell script on boot.

This start up scripts ensures that a there is a cron job configured to push gathered data to the git repo and start the control system.

> [!NOTE]
> A reboot is necessary after running the first time setup script:
>```bash
>sudo reboot
>```

### Configuring the Pi Control System (Chamber Setup)

Once the Pi is configured and all the dependencies are installed, you're ready to configure the control system for the chambers to match your specific experimental setup.

Here is an example configuration for the control system

**Main.py:**
```py
    try:
        # Initialize control system
        control_sys = ControlSystem()
    except Exception as e:
        print(f"Error initializing Control System: {e}")
        return 1
    try:
        # specify each chamber and their corresponding groups
        chamber_list = {    
            "Matcha":       {"group": "Test 1", "slot": 1},
            "Light Roast":  {"group": "Test 2", "slot": 2},
            "Medium Roast": {"group": "Test 1", "slot": 3},
            "Dark Roast":   {"group": "Test 1", "slot": 4}
            }
        
        # add chambers to the control system's active chambers
        print("Adding Chambers")
        for name, kwargs in chamber_list.items():
            control_sys.add_chamber(name, **kwargs)
        
        # start the system
        control_sys.run_sys()
        
    except KeyboardInterrupt:
        print("\nKeyboard Interupt, Gracefully Stopping...")
        control_sys.shut_sys_down()
        return 0
```

The entry name for the `chamber_list` dictionary should match the name sent by the microcontroller (ESP32) in the corresponding chamber. Each chamber's group should match one of the chamber groups specified by the `chamber_groups` parameter in the `config.json`. The slot corresponds to the physical location of the chamber on the test bench, noted by the laser etched C1 through C6 in the laser cutter design for the top of the test bench.

**config.json:**

<hr>
</details>


# Uploading ESP32 Code

### NOTE: When uploading to esp32 feather V2, make sure you don't have an existing serial monitor monitoring it's output, otherwise you may be unable to upload a new program.

**Uploading programs other than main**
```
build_src_filter = ; specify alternate targets to main
    ; +<*> ; add everything
    ; -<test_programs/*> ; remove test programs from scope

    ; uncomment to use test program
    -<main.cpp>
    -<test_programs/*>
    +<test_programs/blinky.cpp>
```
