# voc_detection_system

### NOTE: When uploading to esp32 feather V2, make sure you don't have an existing serial monitor monitoring it's output, otherwise you may be unable to upload a new program.

**It is recommended to use a spare check out of the "raspberry_pi_src" folder on the raspberry pi.** Doing so avoids copying several files and requirements not used on the raspberry pi.
### How to sparse check out:
**1.)** Initialize an empty clone (no files checked out yet):
```bash
git clone --no-checkout https://github.com/jvandag/voc_detection_system
cd voc_detection_system
```

**2.)** Enable sparse‑checkout in “cone” mode (fast path for whole directories):
```bash
git sparse-checkout init --cone
```
Cone mode lets you specify whole directories without complex patterns. 

**3.)** Select the folder you care about (e.g. path/to/folder). If you cloned you're cloning to your home directory, like recommended, this would be `~/voc_detection_system/raspberry_pi_src`:
```bash
git sparse-checkout set ~/voc_detection_system/raspberry_pi_src
```
Now your working tree will contain only that folder (and the usual .git/). 

**4.)** Switch to the branch you want (likely main in this case):
```bash
git checkout main
```
You’ll see only `path/to/folder/` on disk, but Git still knows the full history. 

**Pulling:** `git pull` will fetch updates for the entire repo, but only update your sparse‑checked‑out folder in the working tree.

**Pushing:** `git push` will only send the commits you’ve made (which affect only the sparse‑checked‑out folder) back to origin. You won’t inadvertently delete or modify other directories because you never checked them out or staged changes for them. 


# Uploading ESP32 Code

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