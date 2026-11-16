"""Generates chat-node.kicad_sch. Run: python3 make_sch.py"""
import os
from schgen import Sch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'chat-node.kicad_sch')
PLIB = os.path.join(HERE, '..', 'lib', 'chat-node.kicad_sym')

# net colours (r g b a)
C5V = (200, 30, 30, 1)
C3V = (225, 120, 0, 1)
CUSB = (130, 50, 180, 1)
CMIC = (0, 140, 140, 1)
CAMP = (30, 90, 200, 1)
CSPK = (200, 0, 140, 1)
CCTL = (20, 140, 60, 1)
CLED = (170, 130, 0, 1)
CUART = (120, 90, 60, 1)
BOX = {'pwr': (170, 40, 40, 1), 'reg': (200, 110, 0, 1), 'mcu': (40, 70, 150, 1), 'mic': (0, 120, 120, 1),
       'amp': (150, 0, 110, 1), 'ui': (20, 120, 60, 1), 'tp': (90, 90, 90, 1)}

R0402 = 'Resistor_SMD:R_0402_1005Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
FB0805 = 'Inductor_SMD:L_0805_2012Metric'

PART = {
    '100nF': dict(MPN='CL05B104KO5NNNC', Manufacturer='Samsung Electro-Mechanics', LCSC='C1525'),
    '1uF': dict(MPN='CL05A105KA5NQNC', Manufacturer='Samsung Electro-Mechanics', LCSC='C52923'),
    '10uF': dict(MPN='CL21A106KAYNNNE', Manufacturer='Samsung Electro-Mechanics', LCSC='C15850'),
    '220pF': dict(MPN='GRM1555C1H221JA01D', Manufacturer='Murata Electronics', LCSC='C71693'),
    '5.1k': dict(MPN='0402WGF5101TCE', Manufacturer='UNI-ROYAL', LCSC='C25905'),
    '10k': dict(MPN='0402WGF1002TCE', Manufacturer='UNI-ROYAL', LCSC='C25744'),
    '100k': dict(MPN='0402WGF1003TCE', Manufacturer='UNI-ROYAL', LCSC='C25741'),
    'FB': dict(MPN='HCB2012KF-121T50', Manufacturer='TAI-TECH', LCSC='C304323'),
}

s = Sch('chat-node', 'chat-node: USB-C Wi-Fi voice assistant', paper='A3', rev='1', date='2026-11-11')


def R(ref, val, x, y, horiz=False, side='r', dnp=False):
    """Resistor; side = where the text goes ('r','l' for vertical, 'u','d' for horizontal)."""
    shown = val + ('  DNP' if dnp else '')
    if horiz:
        dy = -1.9 if side == 'u' else 1.9
        return s.sym(ref, 'Device:R_Small_US', x, y, rot=90, value=val, fp=R0402, props=PART[val], dnp=dnp,
                     ref_at=(-2.6, dy, None), val_at=(2.4, dy, None))
    dx, j = (1.9, 'left') if side == 'r' else (-1.9, 'right')
    return s.sym(ref, 'Device:R_Small_US', x, y, value=val, fp=R0402, props=PART[val], dnp=dnp,
                 ref_at=(dx, -1.0, j), val_at=(dx, 1.0, j))


def C(ref, val, x, y, side='r'):
    fp = C0805 if val == '10uF' else C0402
    dx, j = (1.6, 'left') if side == 'r' else (-1.6, 'right')
    return s.sym(ref, 'Device:C_Small', x, y, value=val, fp=fp, props=PART[val],
                 ref_at=(dx, -1.0, j), val_at=(dx, 1.0, j))


def FB(ref, x, y, side='u'):
    d = -1 if side == 'u' else 1
    return s.sym(ref, 'Device:FerriteBead_Small', x, y, rot=90, value='120R@100MHz', fp=FB0805, props=PART['FB'],
                 ref_at=(0, 2.3 * d, None), val_at=(0, 4.3 * d, None))


# =====================================================================
# A. USB-C power input and protection
# =====================================================================
s.box(15.24, 17.78, 114.3, 116.84, 'USB-C INPUT (5 V SINK, USB 2.0)', BOX['pwr'])
J1 = s.sym('J1', 'Connector:USB_C_Receptacle_USB2.0_16P', 35.56, 66.04, value='TYPE-C-31-M-12',
           fp='Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
           props=dict(MPN='TYPE-C-31-M-12', Manufacturer='Korean Hroparts Elec', LCSC='C165948'),
           ref_at=(-10.16, -21.59, 'left'), val_at=(-10.16, -19.56, 'left'))
vb = J1.p('A4')
s.wire(vb, (68.58, vb[1]), color=C5V)
s.pwr('VBUS', (57.15, vb[1]))
s.junction((57.15, vb[1]), C5V)
s.pwr('PWR_FLAG', (63.5, vb[1]))
s.junction((63.5, vb[1]), C5V)
F1 = s.sym('F1', 'Device:Polyfuse_Small', 71.12, vb[1], rot=90, value='2A hold PTC', fp='Fuse:Fuse_1206_3216Metric',
           props=dict(MPN='BSMD1206-200-16V', Manufacturer='BHFUSE', LCSC='C2685749'),
           ref_at=(0, -2.5, None), val_at=(0, 2.6, None))
s.wire((73.66, vb[1]), (96.52, vb[1]), color=C5V)
s.pwr('PWR_FLAG', (86.36, vb[1]))
s.junction((86.36, vb[1]), C5V)
s.pwr('+5V', (96.52, vb[1]))
# CC pull-downs
cc1, cc2 = J1.p('A5'), J1.p('B5')
R1 = R('R1', '5.1k', 58.42, cc1[1], horiz=True, side='u')
R2 = R('R2', '5.1k', 58.42, cc2[1], horiz=True, side='d')
s.wire(cc1, R1.p(1))
s.wire(cc2, R2.p(1))
s.wire(R1.p(2), (66.04, cc1[1]), (66.04, cc2[1]))
s.wire(R2.p(2), (66.04, cc2[1]))
s.wire((66.04, cc2[1]), (68.58, cc2[1]))
s.junction((66.04, cc2[1]))
s.pwr('GND', (68.58, cc2[1]))
# data pair through ESD array
dn_a, dn_b, dp_a, dp_b = J1.p('A7'), J1.p('B7'), J1.p('A6'), J1.p('B6')
U4 = s.sym('U4', 'Power_Protection:USBLC6-2SC6', 86.36, dn_a[1], fp='Package_TO_SOT_SMD:SOT-23-6',
           props=dict(MPN='USBLC6-2SC6', Manufacturer='STMicroelectronics', LCSC='C7519'),
           ref_at=(2.54, -6.6, 'left'), val_at=(2.54, 6.6, 'left'))
x1 = 54.61
s.wire(dn_a, (x1, dn_a[1]), color=CUSB)
s.wire(dn_b, (x1, dn_b[1]), (x1, dn_a[1]), color=CUSB)
s.wire((x1, dn_a[1]), U4.p(1), color=CUSB)
s.junction((x1, dn_a[1]), CUSB)
s.wire(dp_a, (x1, dp_a[1]), color=CUSB)
s.wire(dp_b, (x1, dp_b[1]), (x1, dp_a[1]), color=CUSB)
s.wire((x1, dp_a[1]), (60.96, dp_a[1]), (60.96, U4.p(3)[1]), U4.p(3), color=CUSB)
s.junction((x1, dp_a[1]), CUSB)
s.stub(U4.p(6), 7.62, 'USB_D-', CUSB)
s.stub(U4.p(4), 7.62, 'USB_D+', CUSB)
s.wire(U4.p(5), (86.36, 57.15), color=C5V)
s.pwr('+5V', (86.36, 57.15))
s.pwr('GND', U4.p(2))
s.nc(J1.p('A8'))
s.nc(J1.p('B8'))
g, sh = J1.p('A1'), J1.p('SH')
s.wire(sh, (sh[0], g[1] + 2.54), (g[0], g[1] + 2.54))
s.wire(g, (g[0], g[1] + 2.54))
s.pwr('GND', (g[0], g[1] + 2.54))
s.wire((g[0], g[1] + 2.54), (43.18, g[1] + 2.54))
s.junction((g[0], g[1] + 2.54))
s.pwr('PWR_FLAG', (43.18, g[1] + 2.54))
s.text('5.1k Rd on each CC pin: the source supplies 5 V.\nFirmware keeps the amplifier inside a 500 mA budget\nunless a larger supply is known.', 55.88, 109.22, size=1.27)
s.text('USB 2.0 full speed to the ESP32-S3 native USB\n(programming, console, JTAG).', 55.88, 81.28, size=1.27)

# =====================================================================
# B. 3.3 V regulator
# =====================================================================
s.box(119.38, 17.78, 203.2, 63.5, '3.3 V REGULATOR', BOX['reg'])
U2 = s.sym('U2', 'chat-node:SGM2212-3.3', 161.29, 39.37, libpath=PLIB, value='SGM2212-3.3',
           fp='Package_TO_SOT_SMD:SOT-223-3_TabPin2',
           props=dict(MPN='SGM2212-3.3XKC3G/TR', Manufacturer='SGMICRO', LCSC='C3294699'),
           ref_at=(-3.81, -5.6, 'left'), val_at=(0, -3.4, None))
vi, vo, gn = U2.p(3), U2.p(2), U2.p(1)
s.wire((134.62, vi[1]), vi, color=C5V)
s.pwr('+5V', (134.62, vi[1]))
C1 = C('C1', '10uF', 144.78, vi[1] + 2.54)
s.junction(C1.p(1), C5V)
s.wire(vo, (193.04, vo[1]), color=C3V)
s.pwr('+3V3', (193.04, vo[1]))
C2 = C('C2', '10uF', 176.53, vo[1] + 2.54)
C3 = C('C3', '100nF', 185.42, vo[1] + 2.54)
s.junction(C2.p(1), C3V)
s.junction(C3.p(1), C3V)
yb = C1.p(2)[1] + 2.54
s.wire(C1.p(2), (144.78, yb), (185.42, yb), C3.p(2))
s.wire(C2.p(2), (176.53, yb))
s.wire(gn, (gn[0], yb))
s.junction((gn[0], yb))
s.junction((176.53, yb))
s.pwr('GND', (gn[0], yb))
s.text('Same LDO as Espressif\'s ESP32-S3-DevKitC-1.', 123.19, 60.96, size=1.27)

# =====================================================================
# C. Microphone
# =====================================================================
s.box(119.38, 68.58, 203.2, 116.84, 'I2S MEMS MICROPHONE', BOX['mic'])
MK1 = s.sym('MK1', 'Sensor_Audio:ICS-43434', 165.1, 95.25, fp='Sensor_Audio:InvenSense_ICS-43434-6_3.5x2.65mm',
            props=dict(MPN='ICS-43434', Manufacturer='TDK InvenSense', LCSC='C5656610'),
            ref_at=(1.9, -6.1, 'left'), val_at=(1.9, 6.6, 'left'))
vdd, gnd, lr = MK1.p(5), MK1.p(3), MK1.p(2)
yr = 81.28
s.wire(vdd, (vdd[0], yr), color=C3V)
FB3 = FB('FB3', 138.43, yr, side='d')
s.wire((127.0, yr), FB3.p(1), color=C3V)
s.pwr('+3V3', (127.0, yr))
s.wire(FB3.p(2), (vdd[0], yr), color=C3V)
C7 = C('C7', '1uF', 147.32, yr + 2.54)
C8 = C('C8', '100nF', 154.94, yr + 2.54)
s.junction(C7.p(1), C3V)
s.junction(C8.p(1), C3V)
s.pwr('PWR_FLAG', (160.02, yr))
s.junction((160.02, yr), C3V)
s.wire(C8.p(2), (154.94, yr + 7.62), (147.32, yr + 7.62))
s.wire(C7.p(2), (147.32, yr + 7.62))
s.pwr('GND', (147.32, yr + 7.62))
yg = gnd[1] + 2.54
s.wire(lr, (152.4, lr[1]), (152.4, yg), (gnd[0], yg))
s.wire(gnd, (gnd[0], yg))
s.junction((gnd[0], yg))
s.pwr('GND', (gnd[0], yg))
s.stub(MK1.p(1), 7.62, 'MIC_WS', CMIC)
s.stub(MK1.p(4), 7.62, 'MIC_SCK', CMIC)
sd = MK1.p(6)
s.wire(sd, (190.5, sd[1]), color=CMIC)
s.label('MIC_SD', (190.5, sd[1]), 0, CMIC)
R5 = R('R5', '100k', 185.42, sd[1] + 2.54, side='r')
s.junction(R5.p(1), CMIC)
s.pwr('GND', R5.p(2))
s.text('LR low: data in the left slot.', 121.92, 114.3, size=1.27)

# =====================================================================
# D. ESP32-S3 module
# =====================================================================
s.box(15.24, 121.92, 203.2, 236.22, 'ESP32-S3-WROOM-1-N16R8 (Wi-Fi, native USB)', BOX['mcu'])
U1 = s.sym('U1', 'RF_Module:ESP32-S3-WROOM-1', 115.57, 180.34, value='ESP32-S3-WROOM-1-N16R8',
           fp='RF_Module:ESP32-S3-WROOM-1',
           props=dict(MPN='ESP32-S3-WROOM-1-N16R8', Manufacturer='Espressif Systems', LCSC='C2913202'),
           ref_at=(-12.7, -26.67, 'left'), val_at=(2.54, 26.67, 'left'))
left = {4: ('AMP_SD_MODE', CAMP), 5: ('AMP_DIN', CAMP), 6: ('AMP_BCLK', CAMP), 7: ('AMP_LRCLK', CAMP),
        19: ('MIC_SCK', CMIC), 21: ('MIC_WS', CMIC), 22: ('MIC_SD', CMIC), 8: ('BTN', CCTL), 9: ('LED_DATA', CLED),
        27: ('BOOT', CCTL)}
for pin, (name, col) in left.items():
    s.stub(U1.p(pin), -7.62, name, col)
s.stub(U1.p(13), 7.62, 'USB_D-', CUSB)
s.stub(U1.p(14), 7.62, 'USB_D+', CUSB)
for pin in (39, 38, 15, 12, 17, 18, 20, 10, 11, 23, 36, 37, 28, 29, 30, 31, 32, 33, 34, 35, 26, 16, 24, 25):
    s.nc(U1.p(pin))
# supply + decoupling
v3 = U1.p(2)
ytop = v3[1] - 7.62
s.wire(v3, (v3[0], ytop), color=C3V)
s.pwr('+3V3', (v3[0], ytop))
C5 = C('C5', '10uF', 127.0, v3[1] - 2.54)
C6 = C('C6', '100nF', 135.89, v3[1] - 2.54)
s.wire((v3[0], v3[1] - 5.08), (135.89, v3[1] - 5.08), color=C3V)
s.junction((v3[0], v3[1] - 5.08), C3V)
s.junction(C5.p(1), C3V)
s.wire(C5.p(2), C6.p(2))
s.wire(C6.p(2), (140.97, v3[1]))
s.pwr('GND', (140.97, v3[1]))
s.pwr('GND', U1.p(1))
# reset (EN) network
en = U1.p(3)
s.wire(en, (53.34, en[1]), color=CCTL)
R3 = R('R3', '10k', 86.36, en[1] - 2.54, side='l')
s.junction(R3.p(2), CCTL)
s.pwr('+3V3', R3.p(1))
C4 = C('C4', '1uF', 73.66, en[1] + 2.54, side='l')
s.junction(C4.p(1), CCTL)
s.pwr('GND', C4.p(2))
s.label('EN', (60.96, en[1]), 0, CCTL)
SW2 = s.sym('SW2', 'Switch:SW_Push', 48.26, en[1], value='RESET', fp='Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A',
            props=dict(MPN='TS-1187A-B-A-B', Manufacturer='XKB Connection', LCSC='C318884'),
            ref_at=(0, -6.1, None), val_at=(0, -4.1, None))
s.wire(SW2.p(1), (38.1, en[1]), (38.1, en[1] + 2.54))
s.pwr('GND', (38.1, en[1] + 2.54))
# boot strap
yb0 = 175.26
s.wire((53.34, yb0), (60.96, yb0), color=CCTL)
s.label('BOOT', (60.96, yb0), 0, CCTL)
SW3 = s.sym('SW3', 'Switch:SW_Push', 48.26, yb0, value='BOOT', fp='Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A',
            props=dict(MPN='TS-1187A-B-A-B', Manufacturer='XKB Connection', LCSC='C318884'),
            ref_at=(0, -6.1, None), val_at=(0, -4.1, None))
s.wire(SW3.p(1), (38.1, yb0), (38.1, yb0 + 2.54))
s.pwr('GND', (38.1, yb0 + 2.54))
s.text('GPIO35-37: octal PSRAM inside the module, not usable.\n'
       'GPIO0, 3, 45, 46: strapping pins, left at their defaults\n(GPIO0: BOOT button plus the chip pull-up, as on the DevKitC-1).\n'
       'GPIO8, 9, 10, 12, 17, 18: free for later use. UART0 (GPIO43/44) is unused:\nthe console is the native USB port.\n'
       'Mic on I2S0 and amplifier on I2S1 keep separate clocks,\nso full duplex can be tried later.',
       20.32, 231.14, size=1.27)

# =====================================================================
# E. Audio amplifier
# =====================================================================
s.box(208.28, 17.78, 403.86, 116.84, 'I2S CLASS-D AMPLIFIER AND SPEAKER', BOX['amp'])
U3 = s.sym('U3', 'Audio:MAX98357A', 287.02, 68.58, value='MAX98357AETE+T',
           fp='Package_DFN_QFN:TQFN-16-1EP_3x3mm_P0.5mm_EP1.23x1.23mm',
           props=dict(MPN='MAX98357AETE+T', Manufacturer='Analog Devices / Maxim', LCSC='C910544'),
           ref_at=(-10.16, -11.8, 'left'), val_at=(2.54, -11.8, 'left'))
s.stub(U3.p(1), -7.62, 'AMP_DIN', CAMP)
s.stub(U3.p(16), -7.62, 'AMP_BCLK', CAMP)
s.stub(U3.p(14), -7.62, 'AMP_LRCLK', CAMP)
s.stub(U3.p(4), -7.62, 'AMP_SD_MODE', CAMP)
gp = U3.p(2)
s.wire(gp, (254.0, gp[1]))
R6 = R('R6', '100k', 254.0, gp[1] + 2.54, side='l', dnp=True)
s.pwr('GND', R6.p(2))
vd = U3.p(7)
yv = 45.72
s.wire(vd, (vd[0], yv), (233.68, yv), color=C5V)
s.pwr('+5V', (233.68, yv))
C9 = C('C9', '10uF', 243.84, yv + 2.54)
C11 = C('C11', '100nF', 254.0, yv + 2.54)
for c in (C9, C11):
    s.junction(c.p(1), C5V)
s.wire(C9.p(2), C11.p(2))
s.wire(C9.p(2), (243.84, yv + 7.62))
s.pwr('GND', (243.84, yv + 7.62))
g1, g2 = U3.p(3), U3.p(17)
s.wire(g1, (g1[0], g1[1] + 2.54), (g2[0], g2[1] + 2.54), g2)
s.pwr('GND', (g1[0], g1[1] + 2.54))
# outputs
op, on = U3.p(9), U3.p(10)
FB1 = FB('FB1', 317.5, op[1], side='u')
s.wire(op, FB1.p(1), color=CSPK)
yn = 81.28
FB2 = FB('FB2', 317.5, yn, side='d')
s.wire(on, (302.26, on[1]), (302.26, yn), FB2.p(1), color=CSPK)
C12 = C('C12', '220pF', 330.2, op[1] + 2.54)
C13 = C('C13', '220pF', 330.2, yn - 2.54)
J2 = s.sym('J2', 'Connector_Generic:Conn_01x02', 373.38, 69.85, value='SPEAKER (JST PH)',
           fp='Connector_JST:JST_PH_B2B-PH-SM4-TB_1x02-1MP_P2.00mm_Vertical',
           props=dict(MPN='B2B-PH-SM4-TB(LF)(SN)', Manufacturer='JST', LCSC='C160352'),
           ref_at=(1.27, -4.4, 'left'), val_at=(1.27, 6.4, 'left'))
p1, p2 = J2.p(1), J2.p(2)
s.wire(FB1.p(2), (360.68, op[1]), (360.68, p1[1]), p1, color=CSPK)
s.wire(FB2.p(2), (360.68, yn), (360.68, p2[1]), p2, color=CSPK)
s.junction(C12.p(1), CSPK)
s.junction(C13.p(2), CSPK)
ym = (C12.p(2)[1] + C13.p(1)[1]) / 2
s.wire(C12.p(2), C13.p(1))
s.wire((330.2, 69.85), (335.28, 69.85), (335.28, 72.39))
s.junction((330.2, 69.85))
s.pwr('GND', (335.28, 72.39))
s.label('SPK_P', (339.09, op[1]), 0, CSPK)
s.label('SPK_N', (339.09, yn), 0, CSPK)
s.text('GAIN open: 9 dB. Fit R6 (100k to GND) for 15 dB.\n'
       'SD_MODE has a 100k pull-down inside: amplifier stays off until GPIO4 goes high (left channel).',
       213.36, 111.76, size=1.27)
s.text('Speaker: 40 mm, 4 ohm, 3 W\n(Same Sky CMS-4017-34SP),\nleads on a JST PH plug.', 365.76, 96.52, size=1.27)

# =====================================================================
# G. Button and status LED
# =====================================================================
s.box(208.28, 121.92, 403.86, 185.42, 'MAIN BUTTON AND RGB STATUS LED', BOX['ui'])
SW1 = s.sym('SW1', 'chat-node:SW_Kailh_Choc_V1', 236.22, 152.4, libpath=PLIB, value='Kailh Choc V1',
            fp='chat-node:SW_Kailh_Choc_V1_Reverse',
            props=dict(MPN='CPG135001D01', Manufacturer='Kailh', LCSC='',
                       **{'Customer Note': 'Not fitted by the assembler: plugged in from the back side and hand soldered'}),
            ref_at=(0, -6.1, None), val_at=(0, -4.1, None))
s.wire(SW1.p(1), (226.06, 152.4), (226.06, 154.94))
s.pwr('GND', (226.06, 154.94))
s.stub(SW1.p(2), 7.62, 'BTN', CCTL)
U5 = s.sym('U5', '74xGxx:74AHCT1G125', 304.8, 152.4, value='SN74AHCT1G125', fp='Package_TO_SOT_SMD:SOT-23-5',
           props=dict(MPN='SN74AHCT1G125DBVR', Manufacturer='Texas Instruments', LCSC='C7484'),
           ref_at=(3.81, -6.6, 'left'), val_at=(3.81, 6.6, 'left'))
s.stub(U5.p(2), -5.08, 'LED_DATA', CLED)
R7 = R('R7', '100k', 287.02, 154.94, side='l')
s.junction(R7.p(1), CLED)
s.pwr('GND', R7.p(2))
oe, vcc, ug = U5.p(1), U5.p(5), U5.p(3)
s.wire(oe, (oe[0], 139.7), (314.96, 139.7), (314.96, 142.24))
s.pwr('GND', (314.96, 142.24))
s.wire(vcc, (vcc[0], 134.62), color=C5V)
s.pwr('+5V', (vcc[0], 134.62))
C14 = C('C14', '100nF', 289.56, 139.7, side='l')
s.wire((vcc[0], 137.16), C14.p(1), color=C5V)
s.junction((vcc[0], 137.16), C5V)
s.pwr('GND', C14.p(2))
s.pwr('GND', ug)
D1 = s.sym('D1', 'LED:SK6812MINI-E', 350.52, 152.4, fp='LED_SMD:LED_SK6812MINI-E_3.2x2.8mm_P1.5mm_ReverseMount',
           props=dict(MPN='SK6812MINI-E', Manufacturer='OPSCO Optoelectronics', LCSC='C5149201'),
           ref_at=(5.08, -6.6, 'left'), val_at=(5.08, 6.6, 'left'))
s.wire(U5.p(4), D1.p(2), color=CLED)
s.label('LED_DIN_5V', (322.58, 152.4), 0, CLED)
s.nc(D1.p(4))
dv = D1.p(3)
s.wire(dv, (dv[0], 134.62), color=C5V)
s.pwr('+5V', (dv[0], 134.62))
C15 = C('C15', '100nF', 360.68, 139.7)
s.wire((dv[0], 137.16), C15.p(1), color=C5V)
s.junction((dv[0], 137.16), C5V)
s.pwr('GND', C15.p(2))
s.pwr('GND', D1.p(1))
s.text('SW1 sits on the back of the board (the side facing the lid);\nD1 is reverse mounted and shines up through the board\ninto the switch and the translucent button cap.', 213.36, 180.34, size=1.27)
s.text('The LED runs from 5 V; U5 lifts the\n3.3 V data line to 5 V logic levels.\nR7 holds the line low while the\nmodule boots.', 322.58, 181.61, size=1.27)

# =====================================================================
# F. Test points and mounting
# =====================================================================
s.box(208.28, 190.5, 403.86, 236.22, 'TEST POINTS AND MOUNTING', BOX['tp'])
tps = [('TP1', '+5V', C5V), ('TP2', '+3V3', C3V), ('TP3', 'GND', None), ('TP4', 'EN', CCTL),
       ('TP6', 'MIC_SD', CMIC), ('TP7', 'MIC_SCK', CMIC), ('TP8', 'AMP_DIN', CAMP)]
for i, (ref, net, col) in enumerate(tps):
    cx = 215.9 + (i // 4) * 55.88
    cy = 203.2 + (i % 4) * 6.35
    x2 = cx + 17.78
    s.wire((cx, cy), (x2, cy), color=col)
    s.label(net, (cx, cy), 0, col)
    s.sym(ref, 'Connector:TestPoint', x2, cy, rot=270, value=net, fp='TestPoint:TestPoint_Pad_D1.0mm',
          ref_at=(7.0, 0, None), val_at=(0, 0, None), hide_val=True, in_bom=False)
for i in range(3):
    s.sym('H%d' % (i + 1), 'Mechanical:MountingHole', 340.36 + i * 17.78, 213.36, value='M2',
          fp='MountingHole:MountingHole_2.2mm_M2', ref_at=(0, -4.4, None), val_at=(0, 4.4, None),
          in_bom=False)
s.text('Board mounts with three M2 screws\ninto bosses in the enclosure lid.', 331.47, 229.87, size=1.27)

s.write(OUT)
print('wrote', os.path.normpath(OUT))
