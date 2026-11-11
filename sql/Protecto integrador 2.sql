drop database reportes_laboratorio;
CREATE DATABASE IF NOT EXISTS reportes_laboratorio;
USE reportes_laboratorio;

-- 1. ESTRUCTURA DE TABLAS Y RESTRICCIONES
-- Tabla: PROFESOR
CREATE TABLE profesor (
    carnet_profesor VARCHAR(10)  PRIMARY KEY COMMENT 'Identificador único del profesor (PK)',
    nombres         VARCHAR(60)  NOT NULL COMMENT 'Nombres del profesor',
    apellidos       VARCHAR(60)  NOT NULL COMMENT 'Apellidos del profesor',
    correo          VARCHAR(100) NOT NULL UNIQUE COMMENT 'Correo institucional, debe ser único',
    numero_t        VARCHAR(15)  NULL     COMMENT 'Número telefónico de contacto',
    contrasena_hash VARCHAR(255) NOT NULL COMMENT 'Hash bcrypt de la contraseña',
    estado_cuenta   ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo' COMMENT 'Estado de la cuenta'
) COMMENT = 'Docentes que reportan incidencias detectadas en los laboratorios';

-- Tabla: TECNICO
CREATE TABLE tecnico (
    carnet_tecnico  VARCHAR(10)  PRIMARY KEY COMMENT 'Identificador único del técnico (PK)',
    nombres         VARCHAR(60)  NOT NULL COMMENT 'Nombres del técnico',
    apellidos       VARCHAR(60)  NOT NULL COMMENT 'Apellidos del técnico',
    correo          VARCHAR(100) NOT NULL UNIQUE COMMENT 'Correo institucional, debe ser único',
    telefono        VARCHAR(15)  NULL     COMMENT 'Número telefónico de contacto',
    contrasena_hash VARCHAR(255) NOT NULL COMMENT 'Hash bcrypt de la contraseña',
    estado_cuenta   ENUM('Pendiente','Activo','Inactivo') NOT NULL DEFAULT 'Pendiente' COMMENT 'Estado de la cuenta'
) COMMENT = 'Personal técnico responsable de atender los reportes';

-- Tabla: ADMINISTRADOR
CREATE TABLE administrador (
    carnet_administrador VARCHAR(10)  PRIMARY KEY COMMENT 'Identificador único del administrador (PK)',
    nombres              VARCHAR(60)  NOT NULL COMMENT 'Nombres del administrador',
    apellidos            VARCHAR(60)  NOT NULL COMMENT 'Apellidos del administrador',
    correo               VARCHAR(100) NOT NULL UNIQUE COMMENT 'Correo institucional, debe ser único',
    contrasena_hash      VARCHAR(255) NOT NULL COMMENT 'Hash bcrypt de la contraseña',
    estado_cuenta        ENUM('Pendiente','Activo','Inactivo') NOT NULL DEFAULT 'Pendiente' COMMENT 'Estado de la cuenta'
) COMMENT = 'Administradores del sistema';

-- Tabla: LABORATORIO
CREATE TABLE laboratorio (
    id_laboratorio VARCHAR(10)  PRIMARY KEY COMMENT 'Identificador único del laboratorio (PK)',
    nombre         VARCHAR(60)  NOT NULL COMMENT 'Nombre del laboratorio',
    ubicacion      VARCHAR(100) NULL     COMMENT 'Edificio / piso donde se ubica'
) COMMENT = 'Laboratorios donde pueden generarse reportes de incidencias';

-- Tabla: CATEGORIA
CREATE TABLE categoria (
    id_categoria VARCHAR(10) PRIMARY KEY COMMENT 'Identificador único de la categoría (PK)',
    nombre       VARCHAR(60) NOT NULL COMMENT 'Nombre de la categoría (ej. Hardware, Software, Mobiliario)',
    prioridad    ENUM('Baja','Media','Alta','Crítica') NOT NULL DEFAULT 'Media'
                 COMMENT 'Nivel de prioridad asociado a la categoría'
) COMMENT = 'Categorías de clasificación para los reportes';

-- Tabla: REPORTE
CREATE TABLE reporte (
    id_reporte        INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único del reporte (PK)',
    carnet_profesor   VARCHAR(10)  NOT NULL COMMENT 'Profesor que generó el reporte (FK)',
    carnet_tecnico    VARCHAR(10)  NULL     COMMENT 'Técnico asignado; NULL si aún no se asigna (FK)',
    id_laboratorio    VARCHAR(10)  NOT NULL COMMENT 'Laboratorio donde ocurrió la incidencia (FK)',
    id_categoria      VARCHAR(10)  NOT NULL COMMENT 'Categoría de la incidencia (FK)',
    fecha             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha y hora en que se generó el reporte',
    descripcion       VARCHAR(255) NOT NULL COMMENT 'Descripción breve de la incidencia',
    estado            ENUM('Pendiente','Confirmado','En reparación','En proceso','Resuelto','Reabierto','Cancelado') NOT NULL DEFAULT 'Pendiente'
                       COMMENT 'Estado actual del reporte',
    fecha_resolucion  DATETIME     NULL     COMMENT 'Fecha y hora en que se resolvió el reporte',
    CONSTRAINT fk_reporte_profesor
        FOREIGN KEY (carnet_profesor) REFERENCES profesor(carnet_profesor)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_reporte_tecnico
        FOREIGN KEY (carnet_tecnico) REFERENCES tecnico(carnet_tecnico)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_reporte_laboratorio
        FOREIGN KEY (id_laboratorio) REFERENCES laboratorio(id_laboratorio)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_reporte_categoria
        FOREIGN KEY (id_categoria) REFERENCES categoria(id_categoria)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_reporte_fecha_resolucion
        CHECK (fecha_resolucion IS NULL OR fecha_resolucion >= fecha)
) COMMENT = 'Reportes de incidencias generados en los laboratorios';

-- Tabla: CODIGO_RECUPERACION
CREATE TABLE codigo_recuperacion (
    id_codigo         INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Identificador único del registro (PK)',
    correo             VARCHAR(100) NOT NULL COMMENT 'Correo del usuario que solicita la recuperación',
    codigo_hash        VARCHAR(255) NOT NULL COMMENT 'Código de recuperación almacenado como hash (nunca en texto plano)',
    fecha_expiracion   DATETIME     NOT NULL COMMENT 'Fecha y hora límite de validez del código',
    fecha_creacion     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha y hora en que se generó el código',
    usado              BOOLEAN      NOT NULL DEFAULT FALSE COMMENT 'Indica si el código ya fue utilizado (evita reutilización)',
    INDEX idx_correo (correo),
    CONSTRAINT chk_codigo_fecha_valida
        CHECK (fecha_expiracion > fecha_creacion)
) COMMENT = 'Códigos temporales para el flujo de recuperación de contraseña';


INSERT INTO administrador 
VALUES ('25-04028-0', 'Marlon Samuel', 'Montalvan Bordas', 'marlonbordas10@gmail.com', '040208Neutral', 'Activo');

-- ==========================================
-- 1. INSERTAR ADMINISTRADORES ADICIONALES
-- ==========================================
INSERT INTO administrador (carnet_administrador, nombres, apellidos, correo, contrasena_hash, estado_cuenta) 
VALUES 
('25-04029-0', 'Karina', 'Esquivel Alvarado', 'karina.esquivel@unandemo.edu.ni', '00000001', 'Activo');


-- ==========================================
-- 2. INSERTAR TÉCNICOS
-- ==========================================
INSERT INTO tecnico (carnet_tecnico, nombres, apellidos, correo, telefono, contrasena_hash, estado_cuenta) 
VALUES 
('T-001', 'Lester', 'Chavarría', 'lester.chavarria@unandemo.edu.ni', '88881111', '00000002', 'Activo'),
('T-002', 'Marvin', 'Somarriba', 'marvin.somarriba@unandemo.edu.ni', '88882222', '00000003', 'Activo');


-- ==========================================
-- 3. INSERTAR DOCENTES / PROFESORES
-- ==========================================
INSERT INTO profesor (carnet_profesor, nombres, apellidos, correo, numero_t, contrasena_hash, estado_cuenta) 
VALUES 
('P-101', 'Luis', 'Díaz Beteta', 'luis.diaz@unandemo.edu.ni', '89001001', '00000004', 'Activo'),
('P-102', 'Héctor', 'Somarriba', 'hector.somarriba@unandemo.edu.ni', '89001002', '00000005', 'Activo'),
('P-103', 'Carlos', 'Munguía', 'carlos.munguia@unandemo.edu.ni', '89001003', '00000006', 'Activo'),
('P-104', 'Jacob', 'Narváez', 'jacob.narvaez@unandemo.edu.ni', '89001004', '00000007', 'Activo'),
('P-105', 'Denis', 'Berrios', 'denis.berrios@unandemo.edu.ni', '89001005', '00000008', 'Activo'),
('P-106', 'Davinia', 'Quiroz', 'davinia.quiroz@unandemo.edu.ni', '89001006', '00000009', 'Activo'),
('P-107', 'Jerson', 'Pastran', 'jerson.pastran@unandemo.edu.ni', '89001007', '00000010', 'Activo'),
('P-108', 'Johanna', 'Hernández', 'johanna.hernandez@unandemo.edu.ni', '89001008', '00000011', 'Activo'),
('P-109', 'Ervin', 'Montes', 'ervin.montes@unandemo.edu.ni', '89001009', '00000012', 'Activo'),
('P-110', 'David', 'Maradiaga', 'david.maradiaga@unandemo.edu.ni', '89001010', '00000013', 'Activo'),
('P-111', 'Ernesto', 'Espinoza', 'ernesto.espinoza@unandemo.edu.ni', '89001011', '00000014', 'Activo'),
('P-112', 'Wilmer', 'Matamoros', 'wilmer.matamoros@unandemo.edu.ni', '89001012', '00000015', 'Activo'),
('P-113', 'Álvaro', 'Altamirano', 'alvaro.altamirano@unandemo.edu.ni', '89001013', '00000016', 'Activo');