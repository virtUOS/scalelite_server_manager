# Ansible Module to Manipulate the Scalelite Server API

This repository contains an Ansible module to configure servers in Scalelite using Scalelite's server management API
(see https://github.com/blindsidenetworks/scalelite/blob/master/docs/api-README.md#scalelite-management-using-apis).

## Installation

Copy this file into your `library/` folder of your ansible setup for scalelite and install the (requirements)[requirements.txt].

## Usage

You can now easily add and enable a server like this:
```yaml
# Add a server
- name: Add a bbb host to scalelite and enable it
  scalelite_server_manager:
    bbb_api_url: "https://bbb.example.org/bigbluebutton/api"
    bbb_api_secret: bbb_example_secret
    state: enabled
    scalelite_api_url: "https://my-scalelite.example.org/scalelite/api"
    scalelite_api_secret: scalelite_example_secret
  delegate_to: localhost
```

See the information at the top of the [scalelite_server_manager.py] for more examples and info about the usage.
