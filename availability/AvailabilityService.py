def formatAvailabilityData(availability_tuples):
    formatted_data = []
    for item in availability_tuples:
        formatted_dict = {
            'title': item['shift_name'],
            'start': item['start_time'],
            'end': item['end_time'],
            'color': 'red' if item['availability'] == 0 else 'green',
        }
        formatted_data.append(formatted_dict)
    return formatted_data