#!/usr/bin/env python3

import hashlib
from urllib.parse import urlparse

from ansible.module_utils.basic import AnsibleModule
import requests


DOCUMENTATION = r'''
---
module: scalelite_server_manager

short_description: Manipulate Scalelite's server management API.

version_added: "0.1.0"

description: This module helps to use Scalelite's server management API in
    Ansible.

options:
    bbb_api_url:
        description: The server url in the form:
            `https://my-bbb-host.org/bigbluebutton/api`.
            It will be assumed that the server ID is then
            the host name of the URL (`my-bbb-host.org`
            in this example).
        required: true
        type: str
    state:
        description: The state the server should have in scalelite.
            - With the default value `present` the server will be added
              if it doesn't exist but remains disabled
              (the default in scalelite). If the server already exists,
              its state will not be changed.
            - For `enabled` and `disabled`, if the server does not exist,
              it will be added to scalelite and put in the respective state.
            - If `cordoned` or `panic` is chosen the server already has to
              exist in scalelite beforehand and the module will fail if it
              doesn't.
            - If `absent` is chosen, the server will be deleted from scalelite.
        required: false
        type: str
        default: present
        choices: [ present, absent, enabled, cordoned, disabled, panic ]
    bbb_api_secret:
        description: The api secret of the BigBlueButton server.
            This is required if the server does not yet exist in scalelite
            and the module will fail if it is not present in that case.
            In other cases the secret will be updated accordingly.
        requried: false
        type: str
    load_multiplier:
        description: The server's load multiplier.
        requried: false
        type: float
    scalelite_api_url:
        description: The url of the scalelite API — usually something
        like `https://my-scalelite.example.org/scalelite/api`.
        required: true
        type: str
    scalelite_api_secret:
        description: The secret for the scalelite API.
        required: true
        type: str

author:
    - Timo Nogueira Brockmeyer
'''

EXAMPLES = r'''
# Add a server
- name: Add a bbb host to scalelite and enable it
  scalelite_server_manager:
    bbb_api_url: "https://bbb.example.org/bigbluebutton/api"
    bbb_api_secret: bbb_example_secret
    state: enabled
    scalelite_api_url: "https://my-scalelite.example.org/scalelite/api"
    scalelite_api_secret: scalelite_example_secret
  delegate_to: localhost

# Cordon a server
- name: Cordon a bbb host
  scalelite_server_manager:
    bbb_api_url: "https://bbb.example.org/bigbluebutton/api"
    state: cordoned
    scalelite_api_url: "https://my-scalelite.example.org/scalelite/api"
    scalelite_api_secret: scalelite_example_secret
  delegate_to: localhost

# Update the secret of an existing server
- name: Add a bbb host to scalelite and enable it
  scalelite_server_manager:
    bbb_api_url: "https://bbb.example.org/bigbluebutton/api"
    bbb_api_secret: example_secret
    scalelite_api_url: "https://my-scalelite.example.org/scalelite/api"
    scalelite_api_secret: scalelite_example_secret
  delegate_to: localhost
'''

RETURN = r'''
response:
    description: The response of the scalelite API. See
        the scalelite docs for possible return values.
    type: str
    returned: always
    sample: '
  {
    "id": "bbb.example.org",
    "url": "https://bbb.example.org/bigbluebutton/api",
    "secret": "example_secret",
    "state": "enabled",
    "load": 0.0,
    "load_multiplier": "1.0",
    "online": "online"
  }
    '
'''


def append_checksum(api_call: str, secret: str) -> str:
    """Take a api call and apend the API checksum.

    Args:
        api_call (str): The original API-call.
        secret (str): The API Secret.

    Returns:
        str: The original API-call with the checksum appended.
    """
    parsed_call = urlparse(api_call)
    endpoint = parsed_call.path.split("/")[-1]
    # Generate checksum
    api_string = f"{endpoint}{parsed_call.query}{secret}"
    checksum = hashlib.sha1(str.encode(api_string)).hexdigest()
    # Return call with appended checksum
    if parsed_call.query:
        return f"{api_call}&checksum={checksum}"
    else:
        return f"{api_call}?checksum={checksum}"


def get_servers() -> dict:
    """Get the current status of all BBB servers in scalelite.

    Returns:
        dict: The response object of the request.
    """
    request_url = f"{SCALELITE_URL}/getServers"
    r = requests.get(append_checksum(request_url, SCALELITE_SECRET))
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as error:
        if r.status_code == 404:
            return {}
        raise error
    return r.json()


def post(path: str, payload: dict) -> dict:
    """A custom method for post requests to scalelite.

    Args:
        path (str): The API endpoint to call, e.g. '/addServer'.
        payload (dict): The payload for the request.

    Returns:
        dict: The response object of the request.
    """
    url = append_checksum(f"{SCALELITE_URL}{path}", SCALELITE_SECRET)
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return r.json()


def add_server(server_url: str,
               server_secret: str,
               load_multiplier: float = None) -> dict:
    """Add a BBB server to scalelite.

    Args:
        server_url (str): The API url of the BBB server.
        server_secret (str): The API secret of the BBB server in the
            form 'https://my-bbb-host.org/bigbluebutton/api'.
        load_multiplier (float, optional): The load multiplier of the
            BBB server. Defaults to None.

    Returns:
        dict: The response object of the request.
    """
    payload = {
        "server":
            {"url": server_url,
             "secret": server_secret,
             **({"load_multiplier": load_multiplier} if load_multiplier else {})  # noqa:line-length
             }
    }
    return post('/addServer', payload)


def get_update_dict(current_state: dict, params: dict) -> dict:
    """Create the object used to update the server.

    Args:
        current_state (dict): The current state of the server.
        params (dict): The state specified via the ansible module.params.

    Returns:
        dict: The object containing the update information.
            Empty if there is nothing to update.
    """
    state = {}
    secret = {}
    load_multiplier = {}
    if params['state'] == 'enabled' != current_state['state']:
        state = {'state': 'enable'}
    elif params['state'] == 'disabled' != current_state['state']:
        state = {'state': 'disable'}
    elif params['state'] == 'cordoned' != current_state['state']:
        state = {'state': 'cordon'}
    if params['bbb_api_secret'] and params['bbb_api_secret'] != current_state['secret']:  # noqa:line-length
        secret = {'secret': params['bbb_api_secret']}
    if params['load_multiplier'] and current_state['load_multiplier'] != str(params['load_multiplier']):  # noqa:line-length
        load_multiplier = {"load_multiplier": params['load_multiplier']}
    return {**(state), **(secret), **(load_multiplier)}


def update_server(server_id: str, update_dict: str) -> dict:
    """Update a server.

    Args:
        server_id (str): The ID of the server in scalelite.
        update_dict (str): The object containing the update Information.

    Returns:
        dict: The response object of the request.
    """
    payload = {
        "id": server_id,
        "server": update_dict
    }
    return post('/updateServer', payload)


def delete_server(server_id: str) -> dict:
    """Delete a server from scalelite.

    Args:
        server_id (str): The ID of the server in scalelite.

    Returns:
        dict: The response object of the request.
    """
    payload = {
        "id": server_id
    }
    return post('/deleteServer', payload)


def panic_server(server_id: str) -> dict:
    """Panic a server.

    Args:
        server_id (str): The ID of the server in scalelite.

    Returns:
        dict: The response object of the request.
    """
    payload = {
        "id": server_id
    }
    return post('/panicServer', payload)


def main():

    module = AnsibleModule(
        argument_spec=dict(
            bbb_api_url=dict(type='str', required=True),
            state=dict(type='str', choices=['present', 'absent', 'enabled', 'cordoned', 'disabled', 'panic']),  # noqa:line-length
            bbb_api_secret=dict(type='str'),
            load_multiplier=dict(type='float'),
            scalelite_api_url=dict(type='str', required=True),
            scalelite_api_secret=dict(type='str', required=True)
        ),
        supports_check_mode=True
    )

    # Preseed module return values
    result = dict(
        changed=False,
        response=None
    )

    global SCALELITE_SECRET
    SCALELITE_SECRET = module.params['scalelite_api_secret']
    global SCALELITE_URL
    SCALELITE_URL = module.params['scalelite_api_url']

    server_id = urlparse(module.params['bbb_api_url']).hostname
    servers = get_servers()
    # Retrieve the current server state if it exists:
    server_state = next((s for s in servers if s["id"] == server_id), None)

    # Decide what to do if the server does not exist:
    if not server_state:
        # If the server does not exist and it should be 'absent' we are done:
        if module.params['state'] == 'absent':
            module.exit_json(**result)
        # If the server does not exist but it should, we fail:
        elif module.params['state'] in ['cordoned', 'panic']:
            module.fail_json(
                msg=f"The server you want to set to '{module.params['state']}' does not exist!",  # noqa:line-length
                **result)
        # In the other cases the server should be added:
        else:
            result['changed'] = True
            if module.check_mode:
                module.exit_json(**result)
            server_state = add_server(module.params['bbb_api_url'],
                                      module.params['bbb_api_secret'],
                                      module.params['load_multiplier'])

    # If we are here the server already exists

    # If the server should be absent, delete it and exit:
    if module.params['state'] == 'absent':
        result['changed'] = True
        if module.check_mode:
            module.exit_json(**result)
        result['response'] = delete_server(server_id)
        module.exit_json(**result)

    # If the server should be panicked, do it and exit:
    if module.params['state'] == 'panic':
        result['changed'] = True
        if module.check_mode:
            module.exit_json(**result)
        result['response'] = panic_server(server_id)
        module.exit_json(**result)

    # Create update object
    update_dict = get_update_dict(server_state, module.params)

    # Exit if nothing has changed
    if not update_dict:
        module.exit_json(**result)

    # Update server and exit
    result['changed'] = True
    if module.check_mode:
        module.exit_json(**result)
    result['response'] = update_server(server_id, update_dict)
    module.exit_json(**result)


if __name__ == '__main__':
    main()
