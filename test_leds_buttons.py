from gpiozero import LED, Button
from time import sleep

#GPIO pin setup for LEDs and Buttons
status_led = LED(18)
progress_led = LED(27)
error_led = LED(22)
src_mounted_led=LED(23)
dest_mounted_led=LED(24)

go_button = Button(4,hold_time=1,hold_repeat=False)
cancel_button = Button(17,hold_time=1,hold_repeat=False)
eject_button = Button(5,hold_time=1,hold_repeat=False)
power_button = Button(3,hold_time=1,hold_repeat=False)
btns = [go_button, cancel_button, eject_button, power_button]
btn_names = ['go button', 'cancel button', 'eject button', 'power button']

print('turning all LEDs on')
status_led.on()
progress_led.on()
error_led.on()
src_mounted_led.on()
dest_mounted_led.on()

print('listening for buttons')
while True:
    sleep(0.05)
    for i,button in enumerate(btns):
        if button.is_pressed:
            button.wait_for_release(1)
            if button.is_held:
                print(f'{btn_names[i]} held')
            else:
                print(f'{btn_names[i]} pressed')

