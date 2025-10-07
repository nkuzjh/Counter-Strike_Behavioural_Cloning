# CSGO^2: CrosS-view GeOlocalization based on Counter-Strike: Global Offensive in-game scenes



## Contents

1. [Code Overview](#code-overview)
3. [Data Collect](#data-collect)
4. [Requirements](#requirements)
5. [License](#license)
6. [Disclaimer](#disclaimer)
7. [Maintenance](#maintenance)
8. [Troubleshooting](#troubleshooting)



## Code Overview

We briefly describe the workflow: dataset capture -> data processing -> training -> testing.
1) put ```gamestate_integration_umzhh.cfg``` to CS2 game config path, details in ```meta_utils.py```.
2) Use ```dm_record_data.py``` to scrape data as a spectator, or ```dm_record_data_me_wasd.py``` to record when actively playing. This creates .npy files with screenshots and metadata.
3) [TODO] Run ```dm_infer_actions.py``` on .npy files from step 1 to infer actions from the metadata ('inverse dynamics model'). These are appended to the same .npy files. The visulations and stats produced by this script can be used to clean the data -- e.g. if the metadata from GSI and RAM disagrees for some variables, this is a sign that the data might be unreliable, if there are long periods of immobility (```vel_static```), this can mean you were tracking a motionless player. We suggest deleting such files.
4) [TODO] Run ```dm_pretrain_process.py``` on .npy files from step 2, this creates new .hdf5 files containing screenshots and onehot targets.
5) [TODO] (Optional.) Run ```tools_extract_metaadata.py``` to pull out metadata from the .npy files, saves as new .npy file.


Brief overview of each script's purpose.

- ```gamestate_integration_umzhh.cfg```
    : Contains configuration to get metadata from GS2 Game State Integration(GSI) while playing games.
- ```config.py```
    : Contains key global hyperparameters and settings. Also several functions used across many scripts.
- ```screen_input.py```
    : Gets screenshot of the CSGO window, does some cropping and downsampling. Uses win32gui, win32ui, win32con, OpenCV.
- ```key_output.py```
    : Contains functions to send mouse clicks, set mouse position and key presses. Uses ctypes.
- ```key_output.py```
    : Contains functions to check for mouse location, mouse clicks and key presses. Uses win32api and ctypes.
- ```meta_utils.py```
    : Contains functions to set up RAM reading. Also contains a server class to connect to CSGO's GSI tool -- you should update ```MYTOKENHERE``` variable if setting up GSI.
- ```dm_hazedumper_offsets.py```
    : Contains offsets to read variables from RAM directly. They updated by the function in ```meta_utils.py```.
- ```dm_record_data.py```
    : Records screenshots and metadata when in spectator mode. (Note these record scripts can be temperamental, and depend on hazedumper offsets being up to date.)
- ```dm_record_data_me_wasd.py```
    : Records screenshots and metadata when actively playing on local machine.
- ```dm_infer_actions.py```
    : For recorded dataset, infer actions from metadata and append to same file. Also stats indicative of data quality, and some functionality to rename files sequentially.
- ```dm_pretrain_process.py```
    : Takes .npy files from ```dm_infer_actions.py```, and creates twin .hdf5 files ready for fast data loading with inputs and labels as expected by model. Also a function to strip image from .npy files.
- ```dm_train_model.py```
    : Trains the neural network model. Either from scratch or from a previous checkpoint.
- ```dm_run_agent.py```
    : Runs a trained model in CSGO. Option to collect metadata (eg score) using ```IS_GSI=True```.
- ```tools_dataset_inspect.py```
    : Minimal code to open different datasets and accompanying metadata files.
- ```tools_extract_metadata.py```
    : Cuts out metadata (currvars, infer_a and helper_arr) from the original .npy files, and saves as new .npy without image. Aggregates 100 files together.
- ```tools_dataset_stats.py```
    : Collates metadata from the large online dataset, and produces summary stats and figures as in appendix A.
- ```tools_create_stateful.py```
    : This takes a trained 'non-stateful' model and saves a cloned 'stateful' version that should be used at test time (otherwise LSTM states reset between each forward pass). Required due to keras weirdness.
- ```tools_map_coverage_analysis.py```
    : Visualises map coverage of different agent and datasets, computes Earth mover's distance.
- ```tools_view_save_egs.py```
    : Opens and displays sequences of images .hdf5 and metadata .npy. Option of overlaying inferred actions. Option of saving as .png.
- ```console_csgo_setup.txt```
    : Console commands for setting up CSGO levels.



## Data Collect [TODO]

A brief description of dataset and directory structure is given below.

- screenshots ```*.png```
    - FPS image obtained by grabing CS2 running window with mss library.
    - Cropped and resized to (150, 280, 3).
    - map: as per filename
    - gamemode: as per filename
    - source: as per filename

- metadata ```*.npy```
    - metadata obtained by GSI, needs to be further processed into the format required.
    - np.array(dtype=object), size=(1000,2), screenshots and metadata.
    - map: as per filename
    - gamemode: as per filename
    - source: as per filename

- [TODO] hdf5 ```*.hdf5```
    - hdf5 files, containing screenshots and onehot targets, are obtained by running ```dm_pretrain_process.py```.
    - map: as per filename
    - gamemode: as per filename
    - source: manually created, clean actions

### Structure of .hdf5 files (image and action labels):[TODO]

Each file contains an ordered sequence of 1000 frames (~1 minute) of play.
This contains screenshots, as well as processed action labels.
We chose .hdf5 format for fast dataloading, since a subset of frames can be accessed without opening the full file.
The lookup keys are as follows (where i is frame number 0-999)
- **frame_i_x**: is the image
- **frame_i_xaux**: contains actions applied in previous timesteps, as well as health, ammo, and team. see dm_pretrain_preprocess.py for details, note this was not used in our final version of the agent
- **frame_i_y**: contains target actions in flattened vector form; [keys_pressed_onehot, Lclicks_onehot, Rclicks_onehot, mouse_x_onehot, mouse_y_onehot]
- **frame_i_helperarr**: in format [kill_flag, death_flag], each a binary variable, e.g. [1,0] means the player scored a kill and did not die in that timestep

### Structure of .npy files (scraped metadata):[TODO]

Each .npy file contains metadata corresponding to 100 .hdf5 files (as indicated by file name)
They are dictionaries with keys of format: file_numi_frame_j for file number i, and frame number j in 0-999
The values are of format **[curr_vars, infer_a, frame_i_helperarr]** where,
- **curr_vars**: contains a dictionary of the metadata originally scraped -- see dm_record_data.py for details
- **infer_a**: are inferred actions, [keys_pressed,mouse_x,mouse_y,press_mouse_l,press_mouse_r], with mouse_x and y being continuous values and keys_pressed is in string format
- **frame_i_helperarr**: is a repeat of the .hdf5 file



## Requirements

### Python and OS requirements
Below are the Python package versions used in development, which is borrowed from DIAMOND[https://github.com/eloialonso/diamond/tree/csgo]. Maybe there are several missed libraries need to install manually(do not worry compatibility issues). The OS used for interacting with the game (data collecting) was Windows.
```
conda create -n diamond python=3.10
conda activate diamond
pip install:
    gymnasium==0.29.1
    ale-py==0.9.0
    h5py==3.11.0
    huggingface-hub==0.17.2
    hydra-core==1.3
    numpy==1.26.0
    opencv-python==4.10.0.84
    pillow==10.3.0
    pygame==2.5.2
    torch==2.4.1
    torcheval==0.0.7
    tqdm==4.66.4
    wandb==0.17.0
```

### Hardware

CS2 can be running without GPU. But taking care of window ratio and resolution in game setting.

### CS2 requirements

We collected the datasets and conducted testing based on game version : 1.41.1.2/14112 10553 insecure  public. CS2 is continually updated and this may affect performance. Future updates to gameplay may also degrade performance, consider rolling back the CS2 game version in this case.

Game State Integration (GSI) is used to pull out some metadata about the game. The ```dm_run_agent.py``` script is written so that it may be run without installing GSI (option ```IS_GSI```). If you'd like to record data or extract metadata while running the agent, you'll need to set up GSI: https://www.reddit.com/r/GlobalOffensive/comments/cjhcpy/game_state_integration_a_very_large_and_indepth/ and update ```MYTOKENHERE``` in ```meta_utils.py```.

Details in ```meta_utils.py```.



## License[TODO]
This repo can be used for personal projects and open-sourced research. We do not grant a license for its commercial use in any form. If in doubt, please contact us for permission.

[TODO]: Map copyright of Valve



## Disclaimer
Whilst our code is not intended for cheating/hacking purposes, it's possible that Valve may detect the usage of some of these scripts in game (for example simulated mouse movements and RAM parsing) which in turn might lead to suspicion of cheating. We accept no liability for these sort of issues. Use it at your own risk!



## Maintenance
This repo shares code used for _academic research_. It's not production ready. It's unlikely to be robust across operating systems, python versions, python packages, future CS2 updates etc. There's no plan to actively maintain this repo for these purposes, nor to fix minor bugs. If you'd like to help out with this, please reach out.



## Troubleshooting
A few tips that might help get the code working on your local system.
- Ensure you've matched the game settings used. Particularly important are resolution:
    - Game resolution: Normal 4:3, 1024×768, windowed
- Ensure the code can find your game window -- e.g. as the game is updated to CS2, so you should use
```hwin_csgo = win32gui.FindWindow(None,'Counter-Strike 2')```
- Run ```screen_input.py``` directly to test whether screenshots are being captured correctly. As the ```win32ui``` is invalid on CS2, we use ```mss``` library to capture screenshot from game window. Details in ```screen_input.py```.
- Setting ```IS_DEMO=True``` in ```dm_run_agent.py``` should display the input received by the agent and action selection visualisations, which might highlight issues.
- Is the agent processing the actions quickly enough? -- uncomment ```print('arrived later than wanted to :/, took ',round(time.time() - loop_start_time,4))``` in ```config.py``` to display warnings.



## References
- https://github.com/TeaPearce/Counter-Strike_Behavioural_Cloning
- https://github.com/eloialonso/diamond