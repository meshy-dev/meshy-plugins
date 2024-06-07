# meshy-for-blender

## User Documentation
See [Tutorial](https://docs.meshy.ai/meshy-for-blender-text-to-texture).

## Developer Documentation

### Code Design
UI Components:
* `TextToTexturePanel`: Entry point for the Text to Texture feature.
* `TextToModelPanel`: Entry point for the Text to Model feature.

Core operators:
* `SubmitTaskToRemote()`: Submit a task to remote.
* `AcquireResultsFromRemote()`: Download results of a task from remote.
* `RefreshTaskList()`: Refresh the status of the task list.

Authorization:
* `GetApiKey()`: Retrieve the API key from addon preferences.