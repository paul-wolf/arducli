from tqdm import tqdm


def load_parameters(connection):
    parameters = {}
    connection.mav.param_request_list_send(connection.target_system, connection.target_component)
    first_message = connection.recv_match(type="PARAM_VALUE", blocking=True)
    total_params = first_message.param_count
    print(f"Fetching {total_params} parameters...")
    parameters[first_message.param_id.strip("\x00")] = first_message.param_value
    with tqdm(total=total_params, desc="Loading Parameters", unit="param") as pbar:
        pbar.update(1)
        while True:
            message = connection.recv_match(type="PARAM_VALUE", blocking=True)
            if message is not None:
                param_id = message.param_id.strip("\x00")
                param_value = message.param_value
                parameters[param_id] = param_value
                pbar.update(1)
            if message.param_index + 1 == message.param_count:
                break
    print("All parameters received.")
    return parameters
