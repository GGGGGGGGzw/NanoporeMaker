"""
This example demonstrates how to make a graphical interface to preform
IV characteristic measurements. There are a two items that need to be 
changed for your system:

1) Correct the GPIB addresses in IVProcedure.startup for your instruments
2) Correct the directory to save files in MainWindow.queue

Run the program by changing to the directory containing this file and calling:

python iv_keithley.py

"""

import logging
import sys
from time import sleep
import numpy as np
import math

from pymeasure.display.curves import ResultsCurve
from pymeasure.instruments.keithley import Keithley2450
from pymeasure.display.Qt import QtGui
from pymeasure.display.windows import ManagedWindow
from pymeasure.experiment import (
    Procedure, FloatParameter, unique_filename, Results
)

log = logging.getLogger('')
log.addHandler(logging.NullHandler())


class IVProcedure(Procedure):

    max_current = FloatParameter('最大电流', units='A', default=5e-6)
    min_current = FloatParameter('最小电流', units='A', default=1e-8)
    current_step = FloatParameter('电流步长', units='A', default=5e-9)
    delay = FloatParameter('持续时间', units='ms', default=500)
    voltage_range = FloatParameter('电压范围', units='V', default=35)
    thickness = FloatParameter('膜厚', units='nm', default=30)
    conductivity = FloatParameter('电导率', units='S/m', default=10.98)
    target_diameter = FloatParameter('目标孔径', units='nm', default=20)
    choose = FloatParameter('方案选择', units='', default=0)

    DATA_COLUMNS = ['Current (A)', 'Voltage (V)', 'Diameter (nm)']

    def startup(self):
        log.info("Setting up instruments")
        self.smu = Keithley2450('USB0::0x05E6::0x2450::04428520::INSTR')
        self.smu.measure_voltage()

        self.smu.apply_current()
        self.smu.compliance_voltage = self.voltage_range
        self.smu.enable_source()
        sleep(2)

    def execute(self):
        #currents_up = np.arange(self.min_current, self.max_current, self.current_step)
        #currents_down = np.arange(self.max_current, self.min_current, -self.current_step)
        #currents = np.concatenate((currents_up, currents_down))  # Include the reverse

        con = float(self.conductivity)
        thi = float(self.thickness)

        vol_temp = 0

        is_broken = False
        broken_current = 0

        if self.choose>=0:
            currents = np.arange(self.min_current, self.max_current, self.current_step)
            # currents *= 1e-3  # to mA from A
            steps = len(currents)

            log.info("Starting to sweep through current")
            for i, current in enumerate(currents):
                log.debug("Measuring current: %g mA" % current)
                #if is_broken:
                #    self.smu.source_current = current * 0.5
                #else:
                #    self.smu.source_current = current
                self.smu.source_current = current
                # Or use self.source.ramp_to_current(current, delay=0.1)
                sleep(self.delay*1e-3)

                voltage = self.smu.voltage

                #resistance = (1/(2*conductivity*voltage/current)+sqrt(1/(4*conductivity*conductivity*voltage*voltage/(current*current))+4*thickness*1e-9/(pi*conductivity*voltage/current)))*1e9
                #resistance = voltage/current

                #拟合孔径 正负1nA(粗略)
                self.smu.source_current = 1e-9
                sleep(1)
                volpos = self.smu.voltage

                self.smu.source_current = -1e-9
                sleep(1)
                volneg = self.smu.voltage

                vol1 = float(abs(volpos) + abs(volneg))

                cur1 = 2e-9

                # self.smu.measure_voltage(1, 30, True)
                # self.smu.apply_current()
                # self.smu.compliance_voltage = self.voltage_range
                # self.smu.enable_source()
                #
                # log.debug("Measuring current: %g mA" % current)
                # self.smu.source_current = current
                # # Or use self.source.ramp_to_current(current, delay=0.1)
                # sleep(self.delay * 1e-3)
                #
                # voltage = self.smu.voltage

                # # 拟合孔径 正负0.5V
                # self.smu.measure_current()
                # self.smu.apply_voltage()
                # self.smu.enable_source()
                # self.smu.source_voltage = 0.5
                # sleep(0.25)
                # currentpos = self.smu.current
                # self.smu.source_voltage = -0.5
                # sleep(0.25)
                # currentneg = self.smu.current
                #
                # vol2 = 1
                # # cur1 = 10
                # cur2 = (abs(currentpos) + abs(currentneg))
                #
                # diameter = (1 / (2 * con * vol2 / cur2) + math.sqrt(
                #     1 / (4 * con * con * vol2 * vol2 / (cur2 * cur2)) + 4 * thi * 1e-9 / (
                #             math.pi * con * vol2 / cur2))) * 1e9

                diameter = (1/(2*con*vol1/cur1)+math.sqrt(1/(4*con*con*vol1*vol1/(cur1*cur1))+4*thi*1e-9/(math.pi*con*vol1/cur1)))*1e9

                temp = diameter
                data = {
                    'Current (A)': current,
                    'Voltage (V)': voltage,
                    'Diameter (nm)': diameter
                }
                self.emit('results', data)
                self.emit('progress', 100.*i/steps)

                # #若孔径直接达到目标，立即停止
                # if self.target_diameter - temp < 0:
                #     log.warning("Catch stop command in procedure")
                #     break

                #判断，若孔径大于1.5视为击穿，记录击穿电流，进入扩孔阶段
                # if diameter > 1.5:
                #     is_broken = True
                #     broken_current = current
                #     break
                #判断，电压减小超过0.3V视为击穿，记录击穿电流，进入扩孔阶段
                if vol_temp - voltage > 0.3:
                    is_broken = True
                    broken_current = current
                    break
                else:
                   vol_temp = voltage

                if self.should_stop():
                    log.warning("Catch stop command in procedure")
                    break

        #扩孔阶段循环，起始电流为击穿电流
        if is_broken&self.choose<=0:
            #currents1 = np.arange(broken_current, self.max_current, self.current_step)
            currents = np.arange(self.min_current, self.max_current, self.current_step)
            steps = len(currents)

            log.info("Starting to sweep through current")
            for i, current in enumerate(currents):

                self.smu.measure_voltage()
                self.smu.apply_current()
                self.smu.compliance_voltage = self.voltage_range
                self.smu.enable_source()

                # self.smu.measure_current()
                # self.smu.apply_voltage()
                # self.smu.enable_source()
                # self.smu.source_voltage = 5

                log.debug("Measuring current: %g mA" % current)
                self.smu.source_current = current

                # Or use self.source.ramp_to_current(current, delay=0.1)
                sleep(self.delay * 1e-3)
                voltage = self.smu.voltage
                # current = self.smu.current
                # voltage = 5
                # #拟合孔径 正负10nA
                # self.smu.source_current = 10e-9
                # sleep(0.25)
                # volpos2 = self.smu.voltage
                #
                # self.smu.source_current = -10e-9
                # sleep(0.25)
                # volneg2 = self.smu.voltage
                # vol2 = abs(volpos2) + abs(volneg2)
                # cur2 = 20e-9
                #                 print(volpos2)
                #                 print(volneg2)
                #                 print(vol2)
                #                 print(cur2)
                #拟合孔径 正负0.5V
                self.smu.measure_current()
                self.smu.apply_voltage()
                self.smu.enable_source()
                self.smu.source_voltage = 0.5
                sleep(0.5)
                currentpos = self.smu.current

                self.smu.source_voltage = -0.5
                sleep(0.5)
                currentneg = self.smu.current

                vol2 = 1
                # cur1 = 10
                cur2 = (abs(currentpos) + abs(currentneg))
                # print(currentpos)
                # print(currentneg)

                diameter = (1 / (2 * con * vol2 / cur2) + math.sqrt(
                    1 / (4 * con * con * vol2 * vol2 / (cur2 * cur2)) + 4 * thi * 1e-9 / (
                                math.pi * con * vol2 / cur2))) * 1e9

                #diameter = (1 / (2 * con * vol1 / cur1) + math.sqrt(
                #    1 / (4 * con * con * vol1 * vol1 / (cur1 * cur1)) + 4 * thi * 1e-9 / (
                #                math.pi * con * vol1 / cur1))) * 1e9

                temp = diameter
                data = {
                    'Current (A)': current,
                    'Voltage (V)': voltage,
                    'Diameter (nm)': diameter
                }
                self.emit('results', data)
                self.emit('progress', 100. * i / steps)

                if self.should_stop():
                    log.warning("Catch stop command in procedure")
                    break

                #孔径接近目标终止程序
                if self.target_diameter - diameter <= 0:
                   log.warning("Catch stop command in procedure")
                   break

                # if vol_temp - voltage > 0.3:
                #    log.warning("Catch stop command in procedure")
                #    break
                # else:
                #    vol_temp = voltage

    def shutdown(self):
        self.smu.shutdown()
        log.info("Finished")


class MainWindow(ManagedWindow):


    def __init__(self):
        super(MainWindow, self).__init__(
            procedure_class=IVProcedure,
            inputs=[
                'max_current', 'min_current', 'current_step',
                'delay', 'voltage_range','thickness','conductivity','target_diameter','choose'
            ],
            displays=[
                'max_current', 'min_current', 'current_step',
                'delay', 'voltage_range','thickness','conductivity','target_diameter','choose'
            ],
            x_axis='Current (A)',
            y_axis='Voltage (V)'
        )
        self.setWindowTitle('IV Measurement')
        #hbox1 = QtGui.QHBoxLayout()
        #global diameter
        #diameter = 0.0
        #self.nouse_button= QtGui.QPushButton(str(diameter),self)
        #hbox1.addWidget(self.nouse_button)


    def queue(self):
        directory = "./"  # Change this to the desired directory
        filename = unique_filename(directory, prefix='IV')

        #self.nouse_button.setText('已开始')
        procedure = self.make_procedure()
        results = Results(procedure, filename)
        #self.nouse_button.setText(str(ResultsCurve().get_x()))
        experiment = self.new_experiment(results)

        self.manager.queue(experiment)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
