<!-- MANPAGE: BEGIN EXCLUDED SECTION -->
<div align="center">
   <img width="500" alt="rcli Logo" src="https://raw.githubusercontent.com/Desperationis/rcli/main/.github/banner.png">
   <br />
   <h1 align="center">rcli - CLI Interface for rclone</h1>
   <img alt="Demo" src="https://raw.githubusercontent.com/Desperationis/rcli/main/.github/demo.gif">
</div>
<!-- MANPAGE: END EXCLUDED SECTION -->

<br />

`rcli` is a CLI interface for rclone that can:
* Download files and folders
* Search to navigate to a directory
* Cache remotes for quicker access time
* Navigated through vim-like key bindings or arrow keys

## Requirements 
* Python >= 3.8
* rclone >= 1.53 and configured to at least one remote

## Install
To install on any system: 
```
pip install rclonecli
```

or install locally by running:
```
python3 -m build .
pip3 install dist/*.whl
```

or develop locally by simply running:
```
python3 -m rcli
```

## Using
To start `rcli`, run:
```
rcli remote:
```
Where `remote:` is the name of the remote, making sure to include the semicolon. If you are developing on this project, use the `-v` flag to get the output from the `logging` library into a `rcli.log` file. 


## Contributing
If you find or think of a feature that would make `rcli` better, feel free to pull request. 
