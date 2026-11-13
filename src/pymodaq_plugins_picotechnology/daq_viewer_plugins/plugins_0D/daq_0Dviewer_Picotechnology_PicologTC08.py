import numpy as np

from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport
from pymodaq_gui.parameter import Parameter

from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.data import DataFromPlugins

from pymodaq_plugins_picotechnology.hardware.PicoLogTC08 import PicoLogTC08


class DAQ_0DViewer_Picotechnology_PicologTC08(DAQ_Viewer_base):
    """ Instrument plugin class for Picolog TC08 instrument.
    Developed and tested with Python 3.12
    Tested with PyMoDAQ 5.2 and 5.3
    Requires installation of Pico SDK:
        https://www.picotech.com/downloads/sdk-release/pico-software-development-kit-64bit
    """
    params = comon_parameters + [
        {'title': 'Device serial number :', 'name': 'device_serial_number', 'type': 'str'},
        {'title': 'TC type :', 'name': 'tc_type', 'type': 'str', 'value': 'K', 'readonly': True},
        {'title': 'Channels', 'name': 'channels', 'type': 'group', 'children': [
            {'title': f'Channel {i}', 'name': f'channel_{i}', 'type': 'group', 'children': [
                {'title': 'Activated', 'name': 'activated', 'type': 'bool', 'value': False},
                {'title': 'Ch name', 'name': 'ch_name', 'type': 'str', 'value': f'Channel {i}'},
            ]}
            for i in range(1, 9)
        ]},
    ]

    def ini_attributes(self):
        self.controller: PicoLogTC08 = None
        self.serial = self.settings.child("device_serial_number").value()
        self.tc_type = self.settings.child("tc_type").value()

    def commit_settings(self, param: Parameter):

        if param.name() == 'device_serial_number':
            self.serial = param.value()

        elif param.name() == 'activated' and param.parent().name().startswith('channel_'):
            channel_num = int(param.parent().name().split('_')[1])
            is_activated = param.value()
            if self.controller is not None:
                if is_activated:
                    # Active le channel avec le type de thermocouple choisi
                    self.controller.set_channel_specs(channel_num, self.tc_type)
                else:
                    # Désactive le channel (type ' ' ou 0 selon l'API)
                    self.controller.set_channel_specs(channel_num, ' ')

        elif param.name() == 'tc_type': #inutile tant que "tc_type" est en readonly
            self.tc_type = param.value()

    def ini_detector(self, controller=None):
        info = ""
        if self.is_master:
            try:
                serial = self.settings.child("device_serial_number").value().strip()
                self.controller = PicoLogTC08(serial if serial else None)
                # renseigne le champ avec le serial réellement connecté, utile en mode auto
                self.settings.child("device_serial_number").setValue(self.controller.serial_number)
                self.serial = self.controller.serial_number
                for i in range(1, 9):
                    if self.settings['channels', f'channel_{i}', 'activated']:
                        self.controller.set_channel_specs(i, self.tc_type)
                    else:
                        self.controller.set_channel_specs(i, ' ')
                self.controller.set_mains()
                initialized = True
                info = f"PicoLog TC-08 {self.serial} ouvert"
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.emit_status(ThreadCommand('Update_Status', [f"Connexion au PicoLog impossible : {e}"]))
                self.controller = None
                initialized = False
                info = f"Connexion au PicoLog impossible : {e}"
        else:
            self.controller = controller
            initialized = True

        # Initialise les viewers avec le bon nombre de traces
        if initialized:
            try:
                data_init = []
                labels_init = []
                for i in range(1, 9):
                    if self.settings['channels', f'channel_{i}', 'activated']:
                        ch_name = self.settings.child('channels', f'channel_{i}', 'ch_name').value()
                        data_init.append(np.array([0.0]))
                        labels_init.append(ch_name)

                if data_init:  # évite d'émettre une liste vide
                    self.dte_signal_temp.emit(DataToExport(
                        name='Temperature',
                        data=[DataFromPlugins(name='TC08', data=data_init, dim='Data0D', labels=labels_init, units='degC')]
                    ))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.emit_status(ThreadCommand('Update_Status', [f"Erreur init viewer : {e}"]))


        return info, initialized

    def close(self):
        """Terminate the communication protocol"""
        if self.is_master and self.controller is not None:
            self.controller.close_unit()
            self.controller = None

    def grab_data(self, Naverage=1, **kwargs):
        temp_array = self.controller.get_single()
        data_tot = []
        labels = []
        for i in range(1, 9):
            if self.settings['channels', f'channel_{i}', 'activated']:
                ch_name = self.settings.child('channels', f'channel_{i}', 'ch_name').value()
                data_tot.append(np.array([temp_array[i]]))
                labels.append(ch_name)

        self.dte_signal.emit(DataToExport(name='Temperature',
                                          data=[DataFromPlugins(name='TC08',
                                                                data=data_tot,
                                                                dim='Data0D',
                                                                labels=labels,
                                                                units = 'degC')]))

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        return ''


if __name__ == '__main__':
    main(__file__)