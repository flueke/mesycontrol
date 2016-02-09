#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'florianlueke@gmx.net'

threshold_percent = { 'label': '%', 'name': 'percent', 'factor': 256/30.0 }

# Note: The major part of the fpga version equals the hardware version.
# Note2: The fpga version is only readable if the software version is >= 5.3.

idc                   = 20
NUM_CHANNELS          = 16          # number of channels
NUM_GROUPS            =  4          # number of channel groups
GAIN_FACTOR           = 1.22        # gain step factor
GAIN_JUMPER_LIMITS_V  = (1, 100)    # limits of the hardware gain jumpers for voltage input MSCFs
GAIN_JUMPER_LIMITS_C  = (50/1000.0, 20000/1000.0) # gain jumper limits for charge integrating MSCFs in nC

# hardware setting (shaping_time extension) -> list indexed by shaping time register
SHAPING_TIMES_US    = {
        1: [0.125, 0.25, 0.5, 1.0],
        2: [0.25,  0.5,  1.0, 2.0],
        4: [0.5,   1.0,  2.0, 4.0],
        8: [1.0,   2.0,  4.0, 8.0]
        }

# Module settings
MODULE_NAMES     = [ 'F', 'LN' ]
SHAPING_TIMES    = sorted(SHAPING_TIMES_US.keys())
INPUT_TYPES      = [ 'V', 'C' ]
INPUT_CONNECTORS = [ 'L', 'D' ]
DISCRIMINATORS   = [ 'CFD', 'LE' ]
CFD_DELAYS       = [ 30, 60, 120, 200 ]

profile_dict = {
        'name': 'MSCF-16',
        'idc': idc,
        'parameters': [
            # Gain
            { 'address': 0, 'name': 'gain_group0', 'index': 0, 'range': (0, 15)},
            { 'address': 1, 'name': 'gain_group1', 'index': 1, 'range': (0, 15)},
            { 'address': 2, 'name': 'gain_group2', 'index': 2, 'range': (0, 15)},
            { 'address': 3, 'name': 'gain_group3', 'index': 3, 'range': (0, 15)},
            { 'address': 4, 'name': 'gain_common', 'range': (0, 15)},

            # Threshold
            { 'address':  5, 'name': 'threshold_channel0' , 'index': 0,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  6, 'name': 'threshold_channel1' , 'index': 1,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  7, 'name': 'threshold_channel2' , 'index': 2,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  8, 'name': 'threshold_channel3' , 'index': 3,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  9, 'name': 'threshold_channel4' , 'index': 4,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 10, 'name': 'threshold_channel5' , 'index': 5,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 11, 'name': 'threshold_channel6' , 'index': 6,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 12, 'name': 'threshold_channel7' , 'index': 7,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 13, 'name': 'threshold_channel8' , 'index': 8,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 14, 'name': 'threshold_channel9',  'index': 9,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 15, 'name': 'threshold_channel10', 'index': 10, 'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 16, 'name': 'threshold_channel11', 'index': 11, 'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 17, 'name': 'threshold_channel12', 'index': 12, 'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 18, 'name': 'threshold_channel13', 'index': 13, 'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 19, 'name': 'threshold_channel14', 'index': 14, 'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 20, 'name': 'threshold_channel15', 'index': 15, 'range': (0, 255), 'units': [threshold_percent] },
            { 'address': 21, 'name': 'threshold_common'   ,              'range': (0, 255), 'units': [threshold_percent] },

            # PZ value
            { 'address': 22, 'name': 'pz_value_channel0' , 'index': 0,  'range': (0, 255) },
            { 'address': 23, 'name': 'pz_value_channel1' , 'index': 1,  'range': (0, 255) },
            { 'address': 24, 'name': 'pz_value_channel2' , 'index': 2,  'range': (0, 255) },
            { 'address': 25, 'name': 'pz_value_channel3' , 'index': 3,  'range': (0, 255) },
            { 'address': 26, 'name': 'pz_value_channel4' , 'index': 4,  'range': (0, 255) },
            { 'address': 27, 'name': 'pz_value_channel5' , 'index': 5,  'range': (0, 255) },
            { 'address': 28, 'name': 'pz_value_channel6' , 'index': 6,  'range': (0, 255) },
            { 'address': 29, 'name': 'pz_value_channel7' , 'index': 7,  'range': (0, 255) },
            { 'address': 30, 'name': 'pz_value_channel8' , 'index': 8,  'range': (0, 255) },
            { 'address': 31, 'name': 'pz_value_channel9',  'index': 9,  'range': (0, 255) },
            { 'address': 32, 'name': 'pz_value_channel10', 'index': 10, 'range': (0, 255) },
            { 'address': 33, 'name': 'pz_value_channel11', 'index': 11, 'range': (0, 255) },
            { 'address': 34, 'name': 'pz_value_channel12', 'index': 12, 'range': (0, 255) },
            { 'address': 35, 'name': 'pz_value_channel13', 'index': 13, 'range': (0, 255) },
            { 'address': 36, 'name': 'pz_value_channel14', 'index': 14, 'range': (0, 255) },
            { 'address': 37, 'name': 'pz_value_channel15', 'index': 15, 'range': (0, 255) },
            { 'address': 38, 'name': 'pz_value_common'   , 'range': (0, 255) },

            # Shaping time
            { 'address': 39, 'name': 'shaping_time_group0', 'index': 0, 'range': (0, 3) },
            { 'address': 40, 'name': 'shaping_time_group1', 'index': 1, 'range': (0, 3) },
            { 'address': 41, 'name': 'shaping_time_group2', 'index': 2, 'range': (0, 3) },
            { 'address': 42, 'name': 'shaping_time_group3', 'index': 3, 'range': (0, 3) },
            { 'address': 43, 'name': 'shaping_time_common', 'range': (0, 3) },

            # Misc
            { 'address': 44, 'name': 'multiplicity_hi', 'range': (1, 8) },
            { 'address': 45, 'name': 'multiplicity_lo', 'range': (1, 8) },
            { 'address': 46, 'name': 'monitor_channel', 'range': (1, 16)},
            { 'address': 47, 'name': 'single_channel_mode', 'range': (0, 1), 'default': 1 }, # 0=common, 1=individual
            { 'address': 48, 'name': 'rc_enable', 'read_only': True, 'poll': False },
            { 'address': 49, 'name': 'version', 'read_only': True },                    # hw version >= 4, 16*major+minor
            { 'address': 50, 'name': 'blr_threshold', 'range': (0, 255) },              # hw version >= 4
            { 'address': 51, 'name': 'blr_enable', 'range': (0, 1) },                   # hw version >= 4
            { 'address': 52, 'name': 'coincidence_time', 'range': (0, 255),             # hw version >= 4
                    'units': [{'label': 'ns', 'name': 'nanoseconds', 'factor': 255/180.0, 'offset': 20}] },
            { 'address': 53, 'name': 'threshold_offset', 'range': (0, 200), 'default': 100 },   # hw version >= 4
            { 'address': 54, 'name': 'shaper_offset'   , 'range': (0, 200), 'default': 100 },   # hw version >= 4
            { 'address': 55, 'name': 'sumdis_threshold', 'range': (0, 255) },           # hw version >= 4 && hardware_info sumdis bit set
            { 'address': 56, 'name': 'pz_display_range', 'range': (1, 255) },           # ???
            { 'address': 57, 'name': 'ecl_delay_enable', 'range': (0, 1) },             # hw version >= 5
            { 'address': 58, 'name': 'tf_int_time', 'range': (0, 3) },                  # hw version >= 5

            { 'address': 59, 'name': 'pz_mean', 'read_only': True },                    # hw version >= 4 && sw version >= 5.0
            { 'address': 62, 'name': 'trigger_rate', 'read_only': True, 'poll': True },               # hw version >= 4 && fpga firmware >= 4.1
            { 'address': 63, 'name': 'multiplicity_trigger_rate', 'read_only': True, 'poll': True },  # hw version >= 4 && fpga firmware >= 4.1

            { 'address': 78, 'name': 'histogrammer_status', 'read_only': True, 'poll': True },        # hw version >= 4 && sw version >= 5.0
            { 'address': 79, 'name': 'histogram_clear', 'do_not_store': True },         # hw version >= 4 && sw version >= 5.0
            { 'address': 80, 'name': 'histogram0',  'read_only': True, 'index':  0, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 81, 'name': 'histogram1',  'read_only': True, 'index':  1, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 82, 'name': 'histogram2',  'read_only': True, 'index':  2, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 83, 'name': 'histogram3',  'read_only': True, 'index':  3, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 84, 'name': 'histogram4',  'read_only': True, 'index':  4, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 85, 'name': 'histogram5',  'read_only': True, 'index':  5, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 86, 'name': 'histogram6',  'read_only': True, 'index':  6, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 87, 'name': 'histogram7',  'read_only': True, 'index':  7, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 88, 'name': 'histogram8',  'read_only': True, 'index':  8, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 89, 'name': 'histogram9',  'read_only': True, 'index':  9, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 90, 'name': 'histogram10', 'read_only': True, 'index': 10, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 91, 'name': 'histogram11', 'read_only': True, 'index': 11, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 92, 'name': 'histogram12', 'read_only': True, 'index': 12, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 93, 'name': 'histogram13', 'read_only': True, 'index': 13, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 94, 'name': 'histogram14', 'read_only': True, 'index': 14, 'poll': True },   # hw version >= 4 && sw version >= 5.0
            { 'address': 95, 'name': 'histogram15', 'read_only': True, 'index': 15, 'poll': True },   # hw version >= 4 && sw version >= 5.0

            { 'address': 99, 'name': 'copy_function', 'range': (1, 3), 'do_not_store': True },
            { 'address':100, 'name': 'auto_pz', 'poll': True, 'do_not_store': True },

            # Hardware info register:
            # 8 bits: [- | SumDis | - | - | - | Integrating | >= V4 | LN type ]
            { 'address': 253, 'name': 'hardware_info',          'read_only': True }, # sw version >= 5.3

            # 256 * major + minor
            { 'address': 254, 'name': 'fpga_version',           'read_only': True }, # sw version >= 5.3

            # 256 * major + minor
            # This should always yield the same version as the `version'
            # register (49) (although the encoding is different).
            { 'address': 255, 'name': 'cpu_software_version',   'read_only': True }, # sw version >= 5.3
            ],

        'extensions': [
            { 'name': 'gain_jumpers',       'value': [ 1 for i in range(NUM_GROUPS)] },
            { 'name': 'module_name',        'value': 'F' },                             # the mscf16 suffix (F, LN)
            { 'name': 'shaping_time',       'value': 1 },                               # 1, 2, 4, 8
            { 'name': 'input_type',         'value': 'V' },                             # Voltage or Charge integrating
            { 'name': 'input_connector',    'value': 'L' },                             # Lemo or Differential
            { 'name': 'discriminator',      'value': 'CFD' },                           # CFD or LE (leading edge)
            { 'name': 'cfd_delay',          'value': 30, 'values': [30, 60, 120, 200] },                              # CFD delay (30, 60, 120, 200)
            ],
}
