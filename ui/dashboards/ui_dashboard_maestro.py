# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dashboard_maestro.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
    QSpacerItem, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_DashboardMaestroWidget(object):
    def setupUi(self, DashboardMaestroWidget):
        if not DashboardMaestroWidget.objectName():
            DashboardMaestroWidget.setObjectName(u"DashboardMaestroWidget")
        DashboardMaestroWidget.resize(829, 705)
        self.verticalLayout_6 = QVBoxLayout(DashboardMaestroWidget)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")

        # ── Barra superior ──────────────────────────────────────────────────
        self.barra_superior = QFrame(DashboardMaestroWidget)
        self.barra_superior.setObjectName(u"barra_superior")
        self.barra_superior.setFrameShape(QFrame.StyledPanel)
        self.barra_superior.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.barra_superior)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")

        self.titulo_dashboard = QLabel(self.barra_superior)
        self.titulo_dashboard.setObjectName(u"titulo_dashboard")
        self.horizontalLayout_2.addWidget(self.titulo_dashboard)

        self.horizontalSpacer = QSpacerItem(673, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.boton_cerrar_sesion = QPushButton(self.barra_superior)
        self.boton_cerrar_sesion.setObjectName(u"boton_cerrar_sesion")
        self.horizontalLayout_2.addWidget(self.boton_cerrar_sesion)

        self.verticalLayout_6.addWidget(self.barra_superior)

        # ── Fila de resumen ─────────────────────────────────────────────────
        self.fila_resumen = QWidget(DashboardMaestroWidget)
        self.fila_resumen.setObjectName(u"fila_resumen")
        self.horizontalLayout = QHBoxLayout(self.fila_resumen)
        self.horizontalLayout.setObjectName(u"horizontalLayout")

        self.frame_resumen_laboratorios = QFrame(self.fila_resumen)
        self.frame_resumen_laboratorios.setObjectName(u"frame_resumen_laboratorios")
        self.frame_resumen_laboratorios.setFrameShape(QFrame.StyledPanel)
        self.frame_resumen_laboratorios.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.frame_resumen_laboratorios)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.titulo_laboratorios = QLabel(self.frame_resumen_laboratorios)
        self.titulo_laboratorios.setObjectName(u"titulo_laboratorios")
        self.verticalLayout.addWidget(self.titulo_laboratorios)

        self.label_valor_laboratorios = QLabel(self.frame_resumen_laboratorios)
        self.label_valor_laboratorios.setObjectName(u"label_valor_laboratorios")
        self.verticalLayout.addWidget(self.label_valor_laboratorios)

        self.horizontalLayout.addWidget(self.frame_resumen_laboratorios)

        self.frame_resumen_equipos = QFrame(self.fila_resumen)
        self.frame_resumen_equipos.setObjectName(u"frame_resumen_equipos")
        self.frame_resumen_equipos.setFrameShape(QFrame.StyledPanel)
        self.frame_resumen_equipos.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame_resumen_equipos)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.titulo_equipos = QLabel(self.frame_resumen_equipos)
        self.titulo_equipos.setObjectName(u"titulo_equipos")
        self.verticalLayout_2.addWidget(self.titulo_equipos)

        self.label_valor_equipos = QLabel(self.frame_resumen_equipos)
        self.label_valor_equipos.setObjectName(u"label_valor_equipos")
        self.verticalLayout_2.addWidget(self.label_valor_equipos)

        self.horizontalLayout.addWidget(self.frame_resumen_equipos)
        self.horizontalLayout.setStretch(1, 2)

        self.verticalLayout_6.addWidget(self.fila_resumen)

        # ── Mis reportes ────────────────────────────────────────────────────
        self.frame_mis_reportes = QFrame(DashboardMaestroWidget)
        self.frame_mis_reportes.setObjectName(u"frame_mis_reportes")
        self.frame_mis_reportes.setFrameShape(QFrame.StyledPanel)
        self.frame_mis_reportes.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame_mis_reportes)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.titulo_mis_reportes = QLabel(self.frame_mis_reportes)
        self.titulo_mis_reportes.setObjectName(u"titulo_mis_reportes")
        self.verticalLayout_3.addWidget(self.titulo_mis_reportes)

        self.tabla_mis_reportes = QTableWidget(self.frame_mis_reportes)
        if (self.tabla_mis_reportes.columnCount() < 5):
            self.tabla_mis_reportes.setColumnCount(5)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.tabla_mis_reportes.setHorizontalHeaderItem(0, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.tabla_mis_reportes.setHorizontalHeaderItem(1, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.tabla_mis_reportes.setHorizontalHeaderItem(2, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.tabla_mis_reportes.setHorizontalHeaderItem(3, __qtablewidgetitem8)
        __qtablewidgetitem9 = QTableWidgetItem()
        self.tabla_mis_reportes.setHorizontalHeaderItem(4, __qtablewidgetitem9)
        self.tabla_mis_reportes.setObjectName(u"tabla_mis_reportes")
        self.tabla_mis_reportes.setColumnCount(5)
        self.verticalLayout_3.addWidget(self.tabla_mis_reportes)

        self.verticalLayout_6.addWidget(self.frame_mis_reportes)

        # ── Últimos reportes ────────────────────────────────────────────────
        self.frame_ultimos_reportes = QFrame(DashboardMaestroWidget)
        self.frame_ultimos_reportes.setObjectName(u"frame_ultimos_reportes")
        self.frame_ultimos_reportes.setFrameShape(QFrame.StyledPanel)
        self.frame_ultimos_reportes.setFrameShadow(QFrame.Raised)
        self.verticalLayout_5 = QVBoxLayout(self.frame_ultimos_reportes)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.titulo_ultimos_reportes = QLabel(self.frame_ultimos_reportes)
        self.titulo_ultimos_reportes.setObjectName(u"titulo_ultimos_reportes")
        self.verticalLayout_5.addWidget(self.titulo_ultimos_reportes)

        self.lista_ultimos_reportes = QListWidget(self.frame_ultimos_reportes)
        self.lista_ultimos_reportes.setObjectName(u"lista_ultimos_reportes")
        self.verticalLayout_5.addWidget(self.lista_ultimos_reportes)

        self.verticalLayout_6.addWidget(self.frame_ultimos_reportes)

        self.retranslateUi(DashboardMaestroWidget)

        QMetaObject.connectSlotsByName(DashboardMaestroWidget)
    # setupUi

    def retranslateUi(self, DashboardMaestroWidget):
        DashboardMaestroWidget.setWindowTitle(QCoreApplication.translate("DashboardMaestroWidget", u"Form", None))
        self.titulo_dashboard.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Panel del Maestro", None))
        self.boton_cerrar_sesion.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Cerrar sesi\u00f3n", None))
        self.titulo_laboratorios.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Laboratorios", None))
        self.label_valor_laboratorios.setText(QCoreApplication.translate("DashboardMaestroWidget", u"0 operativos", None))
        self.titulo_equipos.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Computadoras", None))
        self.label_valor_equipos.setText(QCoreApplication.translate("DashboardMaestroWidget", u"0 fuera de servicio", None))
        self.titulo_mis_reportes.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Mis reportes", None))
        ___qtablewidgetitem5 = self.tabla_mis_reportes.horizontalHeaderItem(0)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Laboratorio", None))
        ___qtablewidgetitem6 = self.tabla_mis_reportes.horizontalHeaderItem(1)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Equipo", None))
        ___qtablewidgetitem7 = self.tabla_mis_reportes.horizontalHeaderItem(2)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Tipo de problema", None))
        ___qtablewidgetitem8 = self.tabla_mis_reportes.horizontalHeaderItem(3)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Estado", None))
        ___qtablewidgetitem9 = self.tabla_mis_reportes.horizontalHeaderItem(4)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Fecha", None))
        self.titulo_ultimos_reportes.setText(QCoreApplication.translate("DashboardMaestroWidget", u"Reportes de cierre recientes", None))
    # retranslateUi
