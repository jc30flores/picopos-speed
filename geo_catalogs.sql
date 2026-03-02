--
-- PostgreSQL database dump
--

\restrict nkm2P1o9nXlRxGtCDuxMDPiHQF6CPeISHQDpWdyUCuYPCDfyxKARTj6aXZ8aFm4

-- Dumped from database version 16.13 (Ubuntu 16.13-1.pgdg24.04+1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-1.pgdg24.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activities_catalog; Type: TABLE; Schema: public; Owner: jarvis
--

CREATE TABLE public.activities_catalog (
    code character varying(10) NOT NULL,
    description text NOT NULL,
    normalized text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    version integer DEFAULT 1 NOT NULL
);


ALTER TABLE public.activities_catalog OWNER TO jarvis;

--
-- Name: geo_departments; Type: TABLE; Schema: public; Owner: jarvis
--

CREATE TABLE public.geo_departments (
    code character varying(2) NOT NULL,
    name text NOT NULL,
    normalized text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    version integer DEFAULT 1 NOT NULL
);


ALTER TABLE public.geo_departments OWNER TO jarvis;

--
-- Name: geo_municipalities; Type: TABLE; Schema: public; Owner: jarvis
--

CREATE TABLE public.geo_municipalities (
    id integer NOT NULL,
    dept_code character varying(4) NOT NULL,
    muni_code character varying(4) NOT NULL,
    name text NOT NULL,
    normalized text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    version integer DEFAULT 1 NOT NULL
);


ALTER TABLE public.geo_municipalities OWNER TO jarvis;

--
-- Name: geo_municipalities_id_seq; Type: SEQUENCE; Schema: public; Owner: jarvis
--

CREATE SEQUENCE public.geo_municipalities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.geo_municipalities_id_seq OWNER TO jarvis;

--
-- Name: geo_municipalities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jarvis
--

ALTER SEQUENCE public.geo_municipalities_id_seq OWNED BY public.geo_municipalities.id;


--
-- Name: geo_municipalities id; Type: DEFAULT; Schema: public; Owner: jarvis
--

ALTER TABLE ONLY public.geo_municipalities ALTER COLUMN id SET DEFAULT nextval('public.geo_municipalities_id_seq'::regclass);


--
-- Data for Name: activities_catalog; Type: TABLE DATA; Schema: public; Owner: jarvis
--

COPY public.activities_catalog (code, description, normalized, updated_at, version) FROM stdin;
30110	Fabricación de buques	fabricacion de buques	2026-01-09 12:52:15.476768-06	1
43110	Demolición	demolicion	2026-01-09 12:52:15.476768-06	1
81300	Servicio de jardinería	servicio de jardineria	2026-01-09 12:52:15.476768-06	1
01111	Cultivo de cereales excepto arroz y para forrajes	cultivo de cereales excepto arroz y para forrajes	2026-01-09 12:52:15.476768-06	1
01112	Cultivo de legumbres	cultivo de legumbres	2026-01-09 12:52:15.476768-06	1
01113	Cultivo de semillas oleaginosas	cultivo de semillas oleaginosas	2026-01-09 12:52:15.476768-06	1
01114	Cultivo de plantas para la preparación de semillas	cultivo de plantas para la preparacion de semillas	2026-01-09 12:52:15.476768-06	1
01119	Cultivo de otros cereales excepto arroz y forrajeros n.c.p.	cultivo de otros cereales excepto arroz y forrajeros n.c.p.	2026-01-09 12:52:15.476768-06	1
01120	Cultivo de arroz	cultivo de arroz	2026-01-09 12:52:15.476768-06	1
01131	Cultivo de raíces y tubérculos	cultivo de raices y tuberculos	2026-01-09 12:52:15.476768-06	1
01132	Cultivo de brotes, bulbos, vegetales tubérculos y cultivos similares	cultivo de brotes, bulbos, vegetales tuberculos y cultivos similares	2026-01-09 12:52:15.476768-06	1
01133	Cultivo hortícola de fruto	cultivo horticola de fruto	2026-01-09 12:52:15.476768-06	1
01134	Cultivo de hortalizas de hoja y otras hortalizas ncp	cultivo de hortalizas de hoja y otras hortalizas ncp	2026-01-09 12:52:15.476768-06	1
01140	Cultivo de caña de azúcar	cultivo de cana de azucar	2026-01-09 12:52:15.476768-06	1
01150	Cultivo de tabaco	cultivo de tabaco	2026-01-09 12:52:15.476768-06	1
01161	Cultivo de algodón	cultivo de algodon	2026-01-09 12:52:15.476768-06	1
01162	Cultivo de fibras vegetales excepto algodón	cultivo de fibras vegetales excepto algodon	2026-01-09 12:52:15.476768-06	1
01191	Cultivo de plantas no perennes para la producción de semillas y flores	cultivo de plantas no perennes para la produccion de semillas y flores	2026-01-09 12:52:15.476768-06	1
01192	Cultivo de cereales y pastos para la alimentación animal	cultivo de cereales y pastos para la alimentacion animal	2026-01-09 12:52:15.476768-06	1
01199	Producción de cultivos no estacionales ncp	produccion de cultivos no estacionales ncp	2026-01-09 12:52:15.476768-06	1
01220	Cultivo de frutas tropicales	cultivo de frutas tropicales	2026-01-09 12:52:15.476768-06	1
01230	Cultivo de cítricos	cultivo de citricos	2026-01-09 12:52:15.476768-06	1
01240	Cultivo de frutas de pepita y hueso	cultivo de frutas de pepita y hueso	2026-01-09 12:52:15.476768-06	1
01251	Cultivo de frutas ncp	cultivo de frutas ncp	2026-01-09 12:52:15.476768-06	1
01252	Cultivo de otros frutos y nueces de árboles y arbustos	cultivo de otros frutos y nueces de arboles y arbustos	2026-01-09 12:52:15.476768-06	1
01260	Cultivo de frutos oleaginosos	cultivo de frutos oleaginosos	2026-01-09 12:52:15.476768-06	1
01271	Cultivo de café	cultivo de cafe	2026-01-09 12:52:15.476768-06	1
01272	Cultivo de plantas para la elaboración de bebidas excepto café	cultivo de plantas para la elaboracion de bebidas excepto cafe	2026-01-09 12:52:15.476768-06	1
01281	Cultivo de especias y aromáticas	cultivo de especias y aromaticas	2026-01-09 12:52:15.476768-06	1
01282	Cultivo de plantas para la obtención de productos medicinales y farmacéuticos	cultivo de plantas para la obtencion de productos medicinales y farmaceuticos	2026-01-09 12:52:15.476768-06	1
01291	Cultivo de árboles de hule (caucho) para la obtención de látex	cultivo de arboles de hule (caucho) para la obtencion de latex	2026-01-09 12:52:15.476768-06	1
01292	Cultivo de plantas para la obtención de productos químicos y colorantes	cultivo de plantas para la obtencion de productos quimicos y colorantes	2026-01-09 12:52:15.476768-06	1
01299	Producción de cultivos perennes ncp	produccion de cultivos perennes ncp	2026-01-09 12:52:15.476768-06	1
01300	Propagación de plantas	propagacion de plantas	2026-01-09 12:52:15.476768-06	1
01301	Cultivo de plantas y flores ornamentales	cultivo de plantas y flores ornamentales	2026-01-09 12:52:15.476768-06	1
01420	Cría de caballos y otros equinos	cria de caballos y otros equinos	2026-01-09 12:52:15.476768-06	1
01440	Cría de ovejas y cabras	cria de ovejas y cabras	2026-01-09 12:52:15.476768-06	1
01450	Cría de cerdos	cria de cerdos	2026-01-09 12:52:15.476768-06	1
01460	Cría de aves de corral y producción de huevos	cria de aves de corral y produccion de huevos	2026-01-09 12:52:15.476768-06	1
01491	Cría de abejas apicultura para la obtención de miel y otros productos apícolas	cria de abejas apicultura para la obtencion de miel y otros productos apicolas	2026-01-09 12:52:15.476768-06	1
01492	Cría de conejos	cria de conejos	2026-01-09 12:52:15.476768-06	1
01493	Cría de iguanas y garrobos	cria de iguanas y garrobos	2026-01-09 12:52:15.476768-06	1
01494	Cría de mariposas y otros insectos	cria de mariposas y otros insectos	2026-01-09 12:52:15.476768-06	1
01499	Cría y obtención de productos animales n.c.p.	cria y obtencion de productos animales n.c.p.	2026-01-09 12:52:15.476768-06	1
01500	Cultivo de productos agrícolas en combinación con la cría de animales	cultivo de productos agricolas en combinacion con la cria de animales	2026-01-09 12:52:15.476768-06	1
01611	Servicios de maquinaria agrícola	servicios de maquinaria agricola	2026-01-09 12:52:15.476768-06	1
01612	Control de plagas	control de plagas	2026-01-09 12:52:15.476768-06	1
01613	Servicios de riego	servicios de riego	2026-01-09 12:52:15.476768-06	1
01614	Servicios de contratación de mano de obra para la agricultura	servicios de contratacion de mano de obra para la agricultura	2026-01-09 12:52:15.476768-06	1
01619	Servicios agrícolas ncp	servicios agricolas ncp	2026-01-09 12:52:15.476768-06	1
01621	Actividades para mejorar la reproducción, el crecimiento y el rendimiento de los animales y sus productos	actividades para mejorar la reproduccion, el crecimiento y el rendimiento de los animales y sus productos	2026-01-09 12:52:15.476768-06	1
01622	Servicios de mano de obra pecuaria	servicios de mano de obra pecuaria	2026-01-09 12:52:15.476768-06	1
01629	Servicios pecuarios ncp	servicios pecuarios ncp	2026-01-09 12:52:15.476768-06	1
01631	Labores post cosecha de preparación de los productos agrícolas para su comercialización o para la industria	labores post cosecha de preparacion de los productos agricolas para su comercializacion o para la industria	2026-01-09 12:52:15.476768-06	1
01632	Servicio de beneficio de café	servicio de beneficio de cafe	2026-01-09 12:52:15.476768-06	1
01633	Servicio de beneficiado de plantas textiles (incluye el beneficiado cuando este es realizado en la misma explotación agropecuaria)	servicio de beneficiado de plantas textiles (incluye el beneficiado cuando este es realizado en la misma explotacion agropecuaria)	2026-01-09 12:52:15.476768-06	1
01640	Tratamiento de semillas para la propagación	tratamiento de semillas para la propagacion	2026-01-09 12:52:15.476768-06	1
01700	Caza ordinaria y mediante trampas, repoblación de animales de caza y servicios conexos	caza ordinaria y mediante trampas, repoblacion de animales de caza y servicios conexos	2026-01-09 12:52:15.476768-06	1
02100	Silvicultura y otras actividades forestales	silvicultura y otras actividades forestales	2026-01-09 12:52:15.476768-06	1
02200	Extracción de madera	extraccion de madera	2026-01-09 12:52:15.476768-06	1
02300	Recolección de productos diferentes a la madera	recoleccion de productos diferentes a la madera	2026-01-09 12:52:15.476768-06	1
02400	Servicios de apoyo a la silvicultura	servicios de apoyo a la silvicultura	2026-01-09 12:52:15.476768-06	1
03110	Pesca marítima de altura y costera	pesca maritima de altura y costera	2026-01-09 12:52:15.476768-06	1
03120	Pesca de agua dulce	pesca de agua dulce	2026-01-09 12:52:15.476768-06	1
03210	Acuicultura marítima	acuicultura maritima	2026-01-09 12:52:15.476768-06	1
03220	Acuicultura de agua dulce	acuicultura de agua dulce	2026-01-09 12:52:15.476768-06	1
03300	Servicios de apoyo a la pesca y acuicultura	servicios de apoyo a la pesca y acuicultura	2026-01-09 12:52:15.476768-06	1
05100	Extracción de hulla	extraccion de hulla	2026-01-09 12:52:15.476768-06	1
06100	Extracción de petróleo crudo	extraccion de petroleo crudo	2026-01-09 12:52:15.476768-06	1
06200	Extracción de gas natural	extraccion de gas natural	2026-01-09 12:52:15.476768-06	1
07100	Extracción de minerales de hierro	extraccion de minerales de hierro	2026-01-09 12:52:15.476768-06	1
07210	Extracción de minerales de uranio y torio	extraccion de minerales de uranio y torio	2026-01-09 12:52:15.476768-06	1
07290	Extracción de minerales metalíferos no ferrosos	extraccion de minerales metaliferos no ferrosos	2026-01-09 12:52:15.476768-06	1
08100	Extracción de piedra, arena y arcilla	extraccion de piedra, arena y arcilla	2026-01-09 12:52:15.476768-06	1
08910	Extracción de minerales para la fabricación de abonos y productos químicos	extraccion de minerales para la fabricacion de abonos y productos quimicos	2026-01-09 12:52:15.476768-06	1
08920	Extracción y aglomeración de turba	extraccion y aglomeracion de turba	2026-01-09 12:52:15.476768-06	1
08930	Extracción de sal	extraccion de sal	2026-01-09 12:52:15.476768-06	1
08990	Explotación de otras minas y canteras ncp	explotacion de otras minas y canteras ncp	2026-01-09 12:52:15.476768-06	1
09100	Actividades de apoyo a la extracción de petróleo y gas natural	actividades de apoyo a la extraccion de petroleo y gas natural	2026-01-09 12:52:15.476768-06	1
09900	Actividades de apoyo a la explotación de minas y canteras	actividades de apoyo a la explotacion de minas y canteras	2026-01-09 12:52:15.476768-06	1
10101	Servicio de rastros y mataderos de bovinos y porcinos	servicio de rastros y mataderos de bovinos y porcinos	2026-01-09 12:52:15.476768-06	1
10102	Matanza y procesamiento de bovinos y porcinos	matanza y procesamiento de bovinos y porcinos	2026-01-09 12:52:15.476768-06	1
10103	Matanza y procesamientos de aves de corral	matanza y procesamientos de aves de corral	2026-01-09 12:52:15.476768-06	1
10104	Elaboración y conservación de embutidos y tripas naturales	elaboracion y conservacion de embutidos y tripas naturales	2026-01-09 12:52:15.476768-06	1
10105	Servicios de conservación y empaque de carnes	servicios de conservacion y empaque de carnes	2026-01-09 12:52:15.476768-06	1
10106	Elaboración y conservación de grasas y aceites animales	elaboracion y conservacion de grasas y aceites animales	2026-01-09 12:52:15.476768-06	1
10107	Servicios de molienda de carne	servicios de molienda de carne	2026-01-09 12:52:15.476768-06	1
10108	Elaboración de productos de carne ncp	elaboracion de productos de carne ncp	2026-01-09 12:52:15.476768-06	1
10201	Procesamiento y conservación de pescado, crustáceos y moluscos	procesamiento y conservacion de pescado, crustaceos y moluscos	2026-01-09 12:52:15.476768-06	1
10209	Fabricación de productos de pescado ncp	fabricacion de productos de pescado ncp	2026-01-09 12:52:15.476768-06	1
10301	Elaboración de jugos de frutas y hortalizas	elaboracion de jugos de frutas y hortalizas	2026-01-09 12:52:15.476768-06	1
10302	Elaboración y envase de jaleas, mermeladas y frutas deshidratadas	elaboracion y envase de jaleas, mermeladas y frutas deshidratadas	2026-01-09 12:52:15.476768-06	1
10309	Elaboración de productos de frutas y hortalizas n.c.p.	elaboracion de productos de frutas y hortalizas n.c.p.	2026-01-09 12:52:15.476768-06	1
10401	Fabricación de aceites y grasas vegetales y animales comestibles	fabricacion de aceites y grasas vegetales y animales comestibles	2026-01-09 12:52:15.476768-06	1
10402	Fabricación de aceites y grasas vegetales y animales no comestibles	fabricacion de aceites y grasas vegetales y animales no comestibles	2026-01-09 12:52:15.476768-06	1
10409	Servicio de maquilado de aceites	servicio de maquilado de aceites	2026-01-09 12:52:15.476768-06	1
10501	Fabricación de productos lácteos excepto sorbetes y quesos sustitutos	fabricacion de productos lacteos excepto sorbetes y quesos sustitutos	2026-01-09 12:52:15.476768-06	1
10502	Fabricación de sorbetes y helados	fabricacion de sorbetes y helados	2026-01-09 12:52:15.476768-06	1
10503	Fabricación de quesos	fabricacion de quesos	2026-01-09 12:52:15.476768-06	1
10611	Molienda de cereales	molienda de cereales	2026-01-09 12:52:15.476768-06	1
10612	Elaboración de cereales para el desayuno y similares	elaboracion de cereales para el desayuno y similares	2026-01-09 12:52:15.476768-06	1
10613	Servicios de beneficiado de productos agrícolas ncp (excluye Beneficio de azúcar rama 1072 y beneficio de café rama 0163)	servicios de beneficiado de productos agricolas ncp (excluye beneficio de azucar rama 1072 y beneficio de cafe rama 0163)	2026-01-09 12:52:15.476768-06	1
10621	Fabricación de almidón	fabricacion de almidon	2026-01-09 12:52:15.476768-06	1
10628	Servicio de molienda de maíz húmedo molino para nixtamal	servicio de molienda de maiz humedo molino para nixtamal	2026-01-09 12:52:15.476768-06	1
10711	Elaboración de tortillas	elaboracion de tortillas	2026-01-09 12:52:15.476768-06	1
10712	Fabricación de pan, galletas y barquillos	fabricacion de pan, galletas y barquillos	2026-01-09 12:52:15.476768-06	1
10713	Fabricación de repostería	fabricacion de reposteria	2026-01-09 12:52:15.476768-06	1
10721	Ingenios azucareros	ingenios azucareros	2026-01-09 12:52:15.476768-06	1
10722	Molienda de caña de azúcar para la elaboración de dulces	molienda de cana de azucar para la elaboracion de dulces	2026-01-09 12:52:15.476768-06	1
10723	Elaboración de jarabes de azúcar y otros similares	elaboracion de jarabes de azucar y otros similares	2026-01-09 12:52:15.476768-06	1
10724	Maquilado de azúcar de caña	maquilado de azucar de cana	2026-01-09 12:52:15.476768-06	1
10730	Fabricación de cacao, chocolates y productos de confitería	fabricacion de cacao, chocolates y productos de confiteria	2026-01-09 12:52:15.476768-06	1
10740	Elaboración de macarrones, fideos, y productos farináceos similares	elaboracion de macarrones, fideos, y productos farinaceos similares	2026-01-09 12:52:15.476768-06	1
10750	Elaboración de comidas y platos preparados para la reventa en locales y/o para exportación	elaboracion de comidas y platos preparados para la reventa en locales y/o para exportacion	2026-01-09 12:52:15.476768-06	1
10791	Elaboración de productos de café	elaboracion de productos de cafe	2026-01-09 12:52:15.476768-06	1
10792	Elaboración de especies, sazonadores y condimentos	elaboracion de especies, sazonadores y condimentos	2026-01-09 12:52:15.476768-06	1
10793	Elaboración de sopas, cremas y consomé	elaboracion de sopas, cremas y consome	2026-01-09 12:52:15.476768-06	1
10794	Fabricación de bocadillos tostados y/o fritos	fabricacion de bocadillos tostados y/o fritos	2026-01-09 12:52:15.476768-06	1
10799	Elaboración de productos alimenticios ncp	elaboracion de productos alimenticios ncp	2026-01-09 12:52:15.476768-06	1
10800	Elaboración de alimentos preparados para animales	elaboracion de alimentos preparados para animales	2026-01-09 12:52:15.476768-06	1
11012	Fabricación de aguardiente y licores	fabricacion de aguardiente y licores	2026-01-09 12:52:15.476768-06	1
11020	Elaboración de vinos	elaboracion de vinos	2026-01-09 12:52:15.476768-06	1
11030	Fabricación de cerveza	fabricacion de cerveza	2026-01-09 12:52:15.476768-06	1
11041	Fabricación de aguas gaseosas	fabricacion de aguas gaseosas	2026-01-09 12:52:15.476768-06	1
11042	Fabricación y envasado de agua	fabricacion y envasado de agua	2026-01-09 12:52:15.476768-06	1
11043	Elaboración de refrescos	elaboracion de refrescos	2026-01-09 12:52:15.476768-06	1
11048	Maquilado de aguas gaseosas	maquilado de aguas gaseosas	2026-01-09 12:52:15.476768-06	1
11049	Elaboración de bebidas no alcohólicas	elaboracion de bebidas no alcoholicas	2026-01-09 12:52:15.476768-06	1
12000	Elaboración de productos de tabaco	elaboracion de productos de tabaco	2026-01-09 12:52:15.476768-06	1
13111	Preparación de fibras textiles	preparacion de fibras textiles	2026-01-09 12:52:15.476768-06	1
13112	Fabricación de hilados	fabricacion de hilados	2026-01-09 12:52:15.476768-06	1
13120	Fabricación de telas	fabricacion de telas	2026-01-09 12:52:15.476768-06	1
13130	Acabado de productos textiles	acabado de productos textiles	2026-01-09 12:52:15.476768-06	1
13910	Fabricación de tejidos de punto y ganchillo	fabricacion de tejidos de punto y ganchillo	2026-01-09 12:52:15.476768-06	1
13921	Fabricación de productos textiles para el hogar	fabricacion de productos textiles para el hogar	2026-01-09 12:52:15.476768-06	1
13922	Sacos, bolsas y otros artículos textiles	sacos, bolsas y otros articulos textiles	2026-01-09 12:52:15.476768-06	1
13929	Fabricación de artículos confeccionados con materiales textiles, excepto prendas de vestir n.c.p	fabricacion de articulos confeccionados con materiales textiles, excepto prendas de vestir n.c.p	2026-01-09 12:52:15.476768-06	1
13930	Fabricación de tapices y alfombras	fabricacion de tapices y alfombras	2026-01-09 12:52:15.476768-06	1
13941	Fabricación de cuerdas de henequén y otras fibras naturales (lazos, pitas)	fabricacion de cuerdas de henequen y otras fibras naturales (lazos, pitas)	2026-01-09 12:52:15.476768-06	1
13942	Fabricación de redes de diversos materiales	fabricacion de redes de diversos materiales	2026-01-09 12:52:15.476768-06	1
13948	Maquilado de productos trenzables de cualquier material (petates, sillas, etc.)	maquilado de productos trenzables de cualquier material (petates, sillas, etc.)	2026-01-09 12:52:15.476768-06	1
13991	Fabricación de adornos, etiquetas y otros artículos para prendas de vestir	fabricacion de adornos, etiquetas y otros articulos para prendas de vestir	2026-01-09 12:52:15.476768-06	1
13992	Servicio de bordados en artículos y prendas de tela	servicio de bordados en articulos y prendas de tela	2026-01-09 12:52:15.476768-06	1
13999	Fabricación de productos textiles ncp	fabricacion de productos textiles ncp	2026-01-09 12:52:15.476768-06	1
14101	Fabricación de ropa interior, para dormir y similares	fabricacion de ropa interior, para dormir y similares	2026-01-09 12:52:15.476768-06	1
14102	Fabricación de ropa para niños	fabricacion de ropa para ninos	2026-01-09 12:52:15.476768-06	1
14103	Fabricación de prendas de vestir para ambos sexos	fabricacion de prendas de vestir para ambos sexos	2026-01-09 12:52:15.476768-06	1
14104	Confección de prendas a medida	confeccion de prendas a medida	2026-01-09 12:52:15.476768-06	1
14105	Fabricación de prendas de vestir para deportes	fabricacion de prendas de vestir para deportes	2026-01-09 12:52:15.476768-06	1
14106	Elaboración de artesanías de uso personal confeccionadas especialmente de materiales textiles	elaboracion de artesanias de uso personal confeccionadas especialmente de materiales textiles	2026-01-09 12:52:15.476768-06	1
14108	Maquilado de prendas de vestir, accesorios y otros	maquilado de prendas de vestir, accesorios y otros	2026-01-09 12:52:15.476768-06	1
14109	Fabricación de prendas y accesorios de vestir n.c.p.	fabricacion de prendas y accesorios de vestir n.c.p.	2026-01-09 12:52:15.476768-06	1
14200	Fabricación de artículos de piel	fabricacion de articulos de piel	2026-01-09 12:52:15.476768-06	1
14301	Fabricación de calcetines, calcetas, medias (panty house) y otros similares	fabricacion de calcetines, calcetas, medias (panty house) y otros similares	2026-01-09 12:52:15.476768-06	1
14302	Fabricación de ropa interior de tejido de punto	fabricacion de ropa interior de tejido de punto	2026-01-09 12:52:15.476768-06	1
14309	Fabricación de prendas de vestir de tejido de punto ncp	fabricacion de prendas de vestir de tejido de punto ncp	2026-01-09 12:52:15.476768-06	1
15110	Curtido y adobo de cueros; adobo y teñido de pieles	curtido y adobo de cueros; adobo y tenido de pieles	2026-01-09 12:52:15.476768-06	1
15121	Fabricación de maletas, bolsos de mano y otros artículos de marroquinería	fabricacion de maletas, bolsos de mano y otros articulos de marroquineria	2026-01-09 12:52:15.476768-06	1
15122	Fabricación de monturas, accesorios y vainas talabartería	fabricacion de monturas, accesorios y vainas talabarteria	2026-01-09 12:52:15.476768-06	1
15123	Fabricación de artesanías principalmente de cuero natural y sintético	fabricacion de artesanias principalmente de cuero natural y sintetico	2026-01-09 12:52:15.476768-06	1
15128	Maquilado de artículos de cuero natural, sintético y de otros materiales	maquilado de articulos de cuero natural, sintetico y de otros materiales	2026-01-09 12:52:15.476768-06	1
15201	Fabricación de calzado	fabricacion de calzado	2026-01-09 12:52:15.476768-06	1
15202	Fabricación de partes y accesorios de calzado	fabricacion de partes y accesorios de calzado	2026-01-09 12:52:15.476768-06	1
15208	Maquilado de partes y accesorios de calzado	maquilado de partes y accesorios de calzado	2026-01-09 12:52:15.476768-06	1
16100	Aserradero y acepilladura de madera	aserradero y acepilladura de madera	2026-01-09 12:52:15.476768-06	1
16210	Fabricación de madera laminada, terciada, enchapada y contrachapada, paneles para la construcción	fabricacion de madera laminada, terciada, enchapada y contrachapada, paneles para la construccion	2026-01-09 12:52:15.476768-06	1
16220	Fabricación de partes y piezas de carpintería para edificios y construcciones	fabricacion de partes y piezas de carpinteria para edificios y construcciones	2026-01-09 12:52:15.476768-06	1
16230	Fabricación de envases y recipientes de madera	fabricacion de envases y recipientes de madera	2026-01-09 12:52:15.476768-06	1
16292	Fabricación de artesanías de madera, semillas, materiales trenzables	fabricacion de artesanias de madera, semillas, materiales trenzables	2026-01-09 12:52:15.476768-06	1
16299	Fabricación de productos de madera, corcho, paja y materiales trenzables ncp	fabricacion de productos de madera, corcho, paja y materiales trenzables ncp	2026-01-09 12:52:15.476768-06	1
17010	Fabricación de pasta de madera, papel y cartón	fabricacion de pasta de madera, papel y carton	2026-01-09 12:52:15.476768-06	1
17020	Fabricación de papel y cartón ondulado y envases de papel y cartón	fabricacion de papel y carton ondulado y envases de papel y carton	2026-01-09 12:52:15.476768-06	1
17091	Fabricación de artículos de papel y cartón de uso personal y doméstico	fabricacion de articulos de papel y carton de uso personal y domestico	2026-01-09 12:52:15.476768-06	1
17092	Fabricación de productos de papel ncp	fabricacion de productos de papel ncp	2026-01-09 12:52:15.476768-06	1
18110	Impresión	impresion	2026-01-09 12:52:15.476768-06	1
18120	Servicios relacionados con la impresión	servicios relacionados con la impresion	2026-01-09 12:52:15.476768-06	1
18200	Reproducción de grabaciones	reproduccion de grabaciones	2026-01-09 12:52:15.476768-06	1
19100	Fabricación de productos de hornos de coque	fabricacion de productos de hornos de coque	2026-01-09 12:52:15.476768-06	1
19201	Fabricación de combustible	fabricacion de combustible	2026-01-09 12:52:15.476768-06	1
19202	Fabricación de aceites y lubricantes	fabricacion de aceites y lubricantes	2026-01-09 12:52:15.476768-06	1
20111	Fabricación de materias primas para la fabricación de colorantes	fabricacion de materias primas para la fabricacion de colorantes	2026-01-09 12:52:15.476768-06	1
20112	Fabricación de materiales curtientes	fabricacion de materiales curtientes	2026-01-09 12:52:15.476768-06	1
20113	Fabricación de gases industriales	fabricacion de gases industriales	2026-01-09 12:52:15.476768-06	1
20114	Fabricación de alcohol etílico	fabricacion de alcohol etilico	2026-01-09 12:52:15.476768-06	1
20119	Fabricación de sustancias químicas básicas	fabricacion de sustancias quimicas basicas	2026-01-09 12:52:15.476768-06	1
20120	Fabricación de abonos y fertilizantes	fabricacion de abonos y fertilizantes	2026-01-09 12:52:15.476768-06	1
20130	Fabricación de plástico y caucho en formas primarias	fabricacion de plastico y caucho en formas primarias	2026-01-09 12:52:15.476768-06	1
20210	Fabricación de plaguicidas y otros productos químicos de uso agropecuario	fabricacion de plaguicidas y otros productos quimicos de uso agropecuario	2026-01-09 12:52:15.476768-06	1
20220	Fabricación de pinturas, barnices y productos de revestimiento similares; tintas de imprenta y masillas	fabricacion de pinturas, barnices y productos de revestimiento similares; tintas de imprenta y masillas	2026-01-09 12:52:15.476768-06	1
20231	Fabricación de jabones, detergentes y similares para limpieza	fabricacion de jabones, detergentes y similares para limpieza	2026-01-09 12:52:15.476768-06	1
20232	Fabricación de perfumes, cosméticos y productos de higiene y cuidado personal, incluyendo tintes, champú, etc.	fabricacion de perfumes, cosmeticos y productos de higiene y cuidado personal, incluyendo tintes, champu, etc.	2026-01-09 12:52:15.476768-06	1
20291	Fabricación de tintas y colores para escribir y pintar; fabricación de cintas para impresoras	fabricacion de tintas y colores para escribir y pintar; fabricacion de cintas para impresoras	2026-01-09 12:52:15.476768-06	1
20292	Fabricación de productos pirotécnicos, explosivos y municiones	fabricacion de productos pirotecnicos, explosivos y municiones	2026-01-09 12:52:15.476768-06	1
20299	Fabricación de productos químicos n.c.p.	fabricacion de productos quimicos n.c.p.	2026-01-09 12:52:15.476768-06	1
20300	Fabricación de fibras artificiales	fabricacion de fibras artificiales	2026-01-09 12:52:15.476768-06	1
21001	Manufactura de productos farmacéuticos, sustancias químicas y productos botánicos	manufactura de productos farmaceuticos, sustancias quimicas y productos botanicos	2026-01-09 12:52:15.476768-06	1
21008	Maquilado de medicamentos	maquilado de medicamentos	2026-01-09 12:52:15.476768-06	1
22110	Fabricación de cubiertas y cámaras; renovación y recauchutado de cubiertas	fabricacion de cubiertas y camaras; renovacion y recauchutado de cubiertas	2026-01-09 12:52:15.476768-06	1
22190	Fabricación de otros productos de caucho	fabricacion de otros productos de caucho	2026-01-09 12:52:15.476768-06	1
22201	Fabricación de envases plásticos	fabricacion de envases plasticos	2026-01-09 12:52:15.476768-06	1
22202	Fabricación de productos plásticos para uso personal o doméstico	fabricacion de productos plasticos para uso personal o domestico	2026-01-09 12:52:15.476768-06	1
22208	Maquila de plásticos	maquila de plasticos	2026-01-09 12:52:15.476768-06	1
22209	Fabricación de productos plásticos n.c.p.	fabricacion de productos plasticos n.c.p.	2026-01-09 12:52:15.476768-06	1
23101	Fabricación de vidrio	fabricacion de vidrio	2026-01-09 12:52:15.476768-06	1
23102	Fabricación de recipientes y envases de vidrio	fabricacion de recipientes y envases de vidrio	2026-01-09 12:52:15.476768-06	1
23108	Servicio de maquilado	servicio de maquilado	2026-01-09 12:52:15.476768-06	1
23109	Fabricación de productos de vidrio ncp	fabricacion de productos de vidrio ncp	2026-01-09 12:52:15.476768-06	1
23910	Fabricación de productos refractarios	fabricacion de productos refractarios	2026-01-09 12:52:15.476768-06	1
23920	Fabricación de productos de arcilla para la construcción	fabricacion de productos de arcilla para la construccion	2026-01-09 12:52:15.476768-06	1
23931	Fabricación de productos de cerámica y porcelana no refractaria	fabricacion de productos de ceramica y porcelana no refractaria	2026-01-09 12:52:15.476768-06	1
23932	Fabricación de productos de cerámica y porcelana ncp	fabricacion de productos de ceramica y porcelana ncp	2026-01-09 12:52:15.476768-06	1
23940	Fabricación de cemento, cal y yeso	fabricacion de cemento, cal y yeso	2026-01-09 12:52:15.476768-06	1
23950	Fabricación de artículos de hormigón, cemento y yeso	fabricacion de articulos de hormigon, cemento y yeso	2026-01-09 12:52:15.476768-06	1
23960	Corte, tallado y acabado de la piedra	corte, tallado y acabado de la piedra	2026-01-09 12:52:15.476768-06	1
23990	Fabricación de productos minerales no metálicos ncp	fabricacion de productos minerales no metalicos ncp	2026-01-09 12:52:15.476768-06	1
24100	Industrias básicas de hierro y acero	industrias basicas de hierro y acero	2026-01-09 12:52:15.476768-06	1
24200	Fabricación de productos primarios de metales preciosos y metales no ferrosos	fabricacion de productos primarios de metales preciosos y metales no ferrosos	2026-01-09 12:52:15.476768-06	1
24310	Fundición de hierro y acero	fundicion de hierro y acero	2026-01-09 12:52:15.476768-06	1
24320	Fundición de metales no ferrosos	fundicion de metales no ferrosos	2026-01-09 12:52:15.476768-06	1
25111	Fabricación de productos metálicos para uso estructural	fabricacion de productos metalicos para uso estructural	2026-01-09 12:52:15.476768-06	1
25118	Servicio de maquila para la fabricación de estructuras metálicas	servicio de maquila para la fabricacion de estructuras metalicas	2026-01-09 12:52:15.476768-06	1
25120	Fabricación de tanques, depósitos y recipientes de metal	fabricacion de tanques, depositos y recipientes de metal	2026-01-09 12:52:15.476768-06	1
25130	Fabricación de generadores de vapor, excepto calderas de agua caliente para calefacción central	fabricacion de generadores de vapor, excepto calderas de agua caliente para calefaccion central	2026-01-09 12:52:15.476768-06	1
25200	Fabricación de armas y municiones	fabricacion de armas y municiones	2026-01-09 12:52:15.476768-06	1
25910	Forjado, prensado, estampado y laminado de metales; pulvimetalurgia	forjado, prensado, estampado y laminado de metales; pulvimetalurgia	2026-01-09 12:52:15.476768-06	1
25920	Tratamiento y revestimiento de metales	tratamiento y revestimiento de metales	2026-01-09 12:52:15.476768-06	1
25930	Fabricación de artículos de cuchillería, herramientas de mano y artículos de ferretería	fabricacion de articulos de cuchilleria, herramientas de mano y articulos de ferreteria	2026-01-09 12:52:15.476768-06	1
25991	Fabricación de envases y artículos conexos de metal	fabricacion de envases y articulos conexos de metal	2026-01-09 12:52:15.476768-06	1
25992	Fabricación de artículos metálicos de uso personal y/o doméstico	fabricacion de articulos metalicos de uso personal y/o domestico	2026-01-09 12:52:15.476768-06	1
25999	Fabricación de productos elaborados de metal ncp	fabricacion de productos elaborados de metal ncp	2026-01-09 12:52:15.476768-06	1
26100	Fabricación de componentes electrónicos	fabricacion de componentes electronicos	2026-01-09 12:52:15.476768-06	1
26200	Fabricación de computadoras y equipo conexo	fabricacion de computadoras y equipo conexo	2026-01-09 12:52:15.476768-06	1
26300	Fabricación de equipo de comunicaciones	fabricacion de equipo de comunicaciones	2026-01-09 12:52:15.476768-06	1
26400	Fabricación de aparatos electrónicos de consumo para audio, video radio y televisión	fabricacion de aparatos electronicos de consumo para audio, video radio y television	2026-01-09 12:52:15.476768-06	1
26510	Fabricación de instrumentos y aparatos para medir, verificar, ensayar, navegar y de control de procesos industriales	fabricacion de instrumentos y aparatos para medir, verificar, ensayar, navegar y de control de procesos industriales	2026-01-09 12:52:15.476768-06	1
26520	Fabricación de relojes y piezas de relojes	fabricacion de relojes y piezas de relojes	2026-01-09 12:52:15.476768-06	1
26600	Fabricación de equipo médico de irradiación y equipo electrónico de uso médico y terapéutico	fabricacion de equipo medico de irradiacion y equipo electronico de uso medico y terapeutico	2026-01-09 12:52:15.476768-06	1
26700	Fabricación de instrumentos de óptica y equipo fotográfico	fabricacion de instrumentos de optica y equipo fotografico	2026-01-09 12:52:15.476768-06	1
26800	Fabricación de medios magnéticos y ópticos	fabricacion de medios magneticos y opticos	2026-01-09 12:52:15.476768-06	1
27100	Fabricación de motores, generadores, transformadores eléctricos, aparatos de distribución y control de electricidad	fabricacion de motores, generadores, transformadores electricos, aparatos de distribucion y control de electricidad	2026-01-09 12:52:15.476768-06	1
27200	Fabricación de pilas, baterías y acumuladores	fabricacion de pilas, baterias y acumuladores	2026-01-09 12:52:15.476768-06	1
27310	Fabricación de cables de fibra óptica	fabricacion de cables de fibra optica	2026-01-09 12:52:15.476768-06	1
27320	Fabricación de otros hilos y cables eléctricos	fabricacion de otros hilos y cables electricos	2026-01-09 12:52:15.476768-06	1
27330	Fabricación de dispositivos de cableados	fabricacion de dispositivos de cableados	2026-01-09 12:52:15.476768-06	1
27400	Fabricación de equipo eléctrico de iluminación	fabricacion de equipo electrico de iluminacion	2026-01-09 12:52:15.476768-06	1
27500	Fabricación de aparatos de uso doméstico	fabricacion de aparatos de uso domestico	2026-01-09 12:52:15.476768-06	1
27900	Fabricación de otros tipos de equipo eléctrico	fabricacion de otros tipos de equipo electrico	2026-01-09 12:52:15.476768-06	1
28110	Fabricación de motores y turbinas, excepto motores para aeronaves, vehículos automotores y motocicletas	fabricacion de motores y turbinas, excepto motores para aeronaves, vehiculos automotores y motocicletas	2026-01-09 12:52:15.476768-06	1
28120	Fabricación de equipo hidráulico	fabricacion de equipo hidraulico	2026-01-09 12:52:15.476768-06	1
28130	Fabricación de otras bombas, compresores, grifos y válvulas	fabricacion de otras bombas, compresores, grifos y valvulas	2026-01-09 12:52:15.476768-06	1
28140	Fabricación de cojinetes, engranajes, trenes de engranajes y piezas de transmisión	fabricacion de cojinetes, engranajes, trenes de engranajes y piezas de transmision	2026-01-09 12:52:15.476768-06	1
28150	Fabricación de hornos y quemadores	fabricacion de hornos y quemadores	2026-01-09 12:52:15.476768-06	1
28160	Fabricación de equipo de elevación y manipulación	fabricacion de equipo de elevacion y manipulacion	2026-01-09 12:52:15.476768-06	1
28170	Fabricación de maquinaria y equipo de oficina	fabricacion de maquinaria y equipo de oficina	2026-01-09 12:52:15.476768-06	1
28180	Fabricación de herramientas manuales	fabricacion de herramientas manuales	2026-01-09 12:52:15.476768-06	1
28190	Fabricación de otros tipos de maquinaria de uso general	fabricacion de otros tipos de maquinaria de uso general	2026-01-09 12:52:15.476768-06	1
28210	Fabricación de maquinaria agropecuaria y forestal	fabricacion de maquinaria agropecuaria y forestal	2026-01-09 12:52:15.476768-06	1
28220	Fabricación de máquinas para conformar metales y maquinaria herramienta	fabricacion de maquinas para conformar metales y maquinaria herramienta	2026-01-09 12:52:15.476768-06	1
28230	Fabricación de maquinaria metalúrgica	fabricacion de maquinaria metalurgica	2026-01-09 12:52:15.476768-06	1
28240	Fabricación de maquinaria para la explotación de minas y canteras y para obras de construcción	fabricacion de maquinaria para la explotacion de minas y canteras y para obras de construccion	2026-01-09 12:52:15.476768-06	1
28250	Fabricación de maquinaria para la elaboración de alimentos, bebidas y tabaco	fabricacion de maquinaria para la elaboracion de alimentos, bebidas y tabaco	2026-01-09 12:52:15.476768-06	1
28260	Fabricación de maquinaria para la elaboración de productos textiles, prendas de vestir y cueros	fabricacion de maquinaria para la elaboracion de productos textiles, prendas de vestir y cueros	2026-01-09 12:52:15.476768-06	1
28291	Fabricación de máquinas para imprenta	fabricacion de maquinas para imprenta	2026-01-09 12:52:15.476768-06	1
28299	Fabricación de maquinaria de uso especial ncp	fabricacion de maquinaria de uso especial ncp	2026-01-09 12:52:15.476768-06	1
29100	Fabricación vehículos automotores	fabricacion vehiculos automotores	2026-01-09 12:52:15.476768-06	1
29200	Fabricación de carrocerías para vehículos automotores; fabricación de remolques y semiremolques	fabricacion de carrocerias para vehiculos automotores; fabricacion de remolques y semiremolques	2026-01-09 12:52:15.476768-06	1
29300	Fabricación de partes, piezas y accesorios para vehículos automotores	fabricacion de partes, piezas y accesorios para vehiculos automotores	2026-01-09 12:52:15.476768-06	1
30120	Construcción y reparación de embarcaciones de recreo	construccion y reparacion de embarcaciones de recreo	2026-01-09 12:52:15.476768-06	1
30200	Fabricación de locomotoras y de material rodante	fabricacion de locomotoras y de material rodante	2026-01-09 12:52:15.476768-06	1
30300	Fabricación de aeronaves y naves espaciales	fabricacion de aeronaves y naves espaciales	2026-01-09 12:52:15.476768-06	1
30400	Fabricación de vehículos militares de combate	fabricacion de vehiculos militares de combate	2026-01-09 12:52:15.476768-06	1
30910	Fabricación de motocicletas	fabricacion de motocicletas	2026-01-09 12:52:15.476768-06	1
30920	Fabricación de bicicletas y sillones de ruedas para inválidos	fabricacion de bicicletas y sillones de ruedas para invalidos	2026-01-09 12:52:15.476768-06	1
30990	Fabricación de equipo de transporte ncp	fabricacion de equipo de transporte ncp	2026-01-09 12:52:15.476768-06	1
31001	Fabricación de colchones y somier	fabricacion de colchones y somier	2026-01-09 12:52:15.476768-06	1
31002	Fabricación de muebles y otros productos de madera a medida	fabricacion de muebles y otros productos de madera a medida	2026-01-09 12:52:15.476768-06	1
31008	Servicios de maquilado de muebles	servicios de maquilado de muebles	2026-01-09 12:52:15.476768-06	1
31009	Fabricación de muebles ncp	fabricacion de muebles ncp	2026-01-09 12:52:15.476768-06	1
32110	Fabricación de joyas platerías y joyerías	fabricacion de joyas platerias y joyerias	2026-01-09 12:52:15.476768-06	1
32120	Fabricación de joyas de imitación (fantasía) y artículos conexos	fabricacion de joyas de imitacion (fantasia) y articulos conexos	2026-01-09 12:52:15.476768-06	1
32200	Fabricación de instrumentos musicales	fabricacion de instrumentos musicales	2026-01-09 12:52:15.476768-06	1
32301	Fabricación de artículos de deporte	fabricacion de articulos de deporte	2026-01-09 12:52:15.476768-06	1
32308	Servicio de maquila de productos deportivos	servicio de maquila de productos deportivos	2026-01-09 12:52:15.476768-06	1
32401	Fabricación de juegos de mesa y de salón	fabricacion de juegos de mesa y de salon	2026-01-09 12:52:15.476768-06	1
32402	Servicio de maquilado de juguetes y juegos	servicio de maquilado de juguetes y juegos	2026-01-09 12:52:15.476768-06	1
32409	Fabricación de juegos y juguetes n.c.p.	fabricacion de juegos y juguetes n.c.p.	2026-01-09 12:52:15.476768-06	1
32500	Fabricación de instrumentos y materiales médicos y odontológicos	fabricacion de instrumentos y materiales medicos y odontologicos	2026-01-09 12:52:15.476768-06	1
32901	Fabricación de lápices, bolígrafos, sellos y artículos de librería en general	fabricacion de lapices, boligrafos, sellos y articulos de libreria en general	2026-01-09 12:52:15.476768-06	1
32902	Fabricación de escobas, cepillos, pinceles y similares	fabricacion de escobas, cepillos, pinceles y similares	2026-01-09 12:52:15.476768-06	1
32903	Fabricación de artesanías de materiales diversos	fabricacion de artesanias de materiales diversos	2026-01-09 12:52:15.476768-06	1
32904	Fabricación de artículos de uso personal y domésticos n.c.p.	fabricacion de articulos de uso personal y domesticos n.c.p.	2026-01-09 12:52:15.476768-06	1
32905	Fabricación de accesorios para las confecciones y la marroquinería n.c.p.	fabricacion de accesorios para las confecciones y la marroquineria n.c.p.	2026-01-09 12:52:15.476768-06	1
32908	Servicios de maquila ncp	servicios de maquila ncp	2026-01-09 12:52:15.476768-06	1
32909	Fabricación de productos manufacturados n.c.p.	fabricacion de productos manufacturados n.c.p.	2026-01-09 12:52:15.476768-06	1
33110	Reparación y mantenimiento de productos elaborados de metal	reparacion y mantenimiento de productos elaborados de metal	2026-01-09 12:52:15.476768-06	1
33120	Reparación y mantenimiento de maquinaria	reparacion y mantenimiento de maquinaria	2026-01-09 12:52:15.476768-06	1
33130	Reparación y mantenimiento de equipo electrónico y óptico	reparacion y mantenimiento de equipo electronico y optico	2026-01-09 12:52:15.476768-06	1
33140	Reparación y mantenimiento de equipo eléctrico	reparacion y mantenimiento de equipo electrico	2026-01-09 12:52:15.476768-06	1
33150	Reparación y mantenimiento de equipo de transporte, excepto vehículos automotores	reparacion y mantenimiento de equipo de transporte, excepto vehiculos automotores	2026-01-09 12:52:15.476768-06	1
33190	Reparación y mantenimiento de equipos n.c.p.	reparacion y mantenimiento de equipos n.c.p.	2026-01-09 12:52:15.476768-06	1
33200	Instalación de maquinaria y equipo industrial	instalacion de maquinaria y equipo industrial	2026-01-09 12:52:15.476768-06	1
35101	Generación de energía eléctrica	generacion de energia electrica	2026-01-09 12:52:15.476768-06	1
35102	Transmisión de energía eléctrica	transmision de energia electrica	2026-01-09 12:52:15.476768-06	1
35103	Distribución de energía eléctrica	distribucion de energia electrica	2026-01-09 12:52:15.476768-06	1
35200	Fabricación de gas, distribución de combustibles gaseosos por tuberías	fabricacion de gas, distribucion de combustibles gaseosos por tuberias	2026-01-09 12:52:15.476768-06	1
35300	Suministro de vapor y agua caliente	suministro de vapor y agua caliente	2026-01-09 12:52:15.476768-06	1
36000	Captación, tratamiento y suministro de agua	captacion, tratamiento y suministro de agua	2026-01-09 12:52:15.476768-06	1
37000	Evacuación de aguas residuales (alcantarillado)	evacuacion de aguas residuales (alcantarillado)	2026-01-09 12:52:15.476768-06	1
38110	Recolección y transporte de desechos sólidos proveniente de hogares y sector urbano	recoleccion y transporte de desechos solidos proveniente de hogares y sector urbano	2026-01-09 12:52:15.476768-06	1
38120	Recolección de desechos peligrosos	recoleccion de desechos peligrosos	2026-01-09 12:52:15.476768-06	1
38210	Tratamiento y eliminación de desechos inicuos	tratamiento y eliminacion de desechos inicuos	2026-01-09 12:52:15.476768-06	1
38220	Tratamiento y eliminación de desechos peligrosos	tratamiento y eliminacion de desechos peligrosos	2026-01-09 12:52:15.476768-06	1
38301	Reciclaje de desperdicios y desechos textiles	reciclaje de desperdicios y desechos textiles	2026-01-09 12:52:15.476768-06	1
38302	Reciclaje de desperdicios y desechos de plástico y caucho	reciclaje de desperdicios y desechos de plastico y caucho	2026-01-09 12:52:15.476768-06	1
38303	Reciclaje de desperdicios y desechos de vidrio	reciclaje de desperdicios y desechos de vidrio	2026-01-09 12:52:15.476768-06	1
46375	Venta al por mayor de productos lácteos	venta al por mayor de productos lacteos	2026-01-09 12:52:15.476768-06	1
38304	Reciclaje de desperdicios y desechos de papel y cartón	reciclaje de desperdicios y desechos de papel y carton	2026-01-09 12:52:15.476768-06	1
38305	Reciclaje de desperdicios y desechos metálicos	reciclaje de desperdicios y desechos metalicos	2026-01-09 12:52:15.476768-06	1
38309	Reciclaje de desperdicios y desechos no metálicos n.c.p.	reciclaje de desperdicios y desechos no metalicos n.c.p.	2026-01-09 12:52:15.476768-06	1
39000	Actividades de Saneamiento y otros Servicios de Gestión de Desechos	actividades de saneamiento y otros servicios de gestion de desechos	2026-01-09 12:52:15.476768-06	1
41001	Construcción de edificios residenciales	construccion de edificios residenciales	2026-01-09 12:52:15.476768-06	1
41002	Construcción de edificios no residenciales	construccion de edificios no residenciales	2026-01-09 12:52:15.476768-06	1
42100	Construcción de carreteras, calles y caminos	construccion de carreteras, calles y caminos	2026-01-09 12:52:15.476768-06	1
42200	Construcción de proyectos de servicio público	construccion de proyectos de servicio publico	2026-01-09 12:52:15.476768-06	1
42900	Construcción de obras de ingeniería civil n.c.p.	construccion de obras de ingenieria civil n.c.p.	2026-01-09 12:52:15.476768-06	1
43120	Preparación de terreno	preparacion de terreno	2026-01-09 12:52:15.476768-06	1
43210	Instalaciones eléctricas	instalaciones electricas	2026-01-09 12:52:15.476768-06	1
43220	Instalación de fontanería, calefacción y aire acondicionado	instalacion de fontaneria, calefaccion y aire acondicionado	2026-01-09 12:52:15.476768-06	1
43290	Otras instalaciones para obras de construcción	otras instalaciones para obras de construccion	2026-01-09 12:52:15.476768-06	1
43300	Terminación y acabado de edificios	terminacion y acabado de edificios	2026-01-09 12:52:15.476768-06	1
43900	Otras actividades especializadas de construcción	otras actividades especializadas de construccion	2026-01-09 12:52:15.476768-06	1
43901	Fabricación de techos y materiales diversos	fabricacion de techos y materiales diversos	2026-01-09 12:52:15.476768-06	1
45100	Venta de vehículos automotores	venta de vehiculos automotores	2026-01-09 12:52:15.476768-06	1
45201	Reparación mecánica de vehículos automotores	reparacion mecanica de vehiculos automotores	2026-01-09 12:52:15.476768-06	1
45202	Reparaciones eléctricas del automotor y recarga de baterías	reparaciones electricas del automotor y recarga de baterias	2026-01-09 12:52:15.476768-06	1
45203	Enderezado y pintura de vehículos automotores	enderezado y pintura de vehiculos automotores	2026-01-09 12:52:15.476768-06	1
45204	Reparaciones de radiadores, escapes y silenciadores	reparaciones de radiadores, escapes y silenciadores	2026-01-09 12:52:15.476768-06	1
45205	Reparación y reconstrucción de vías, stop y otros artículos de fibra de vidrio	reparacion y reconstruccion de vias, stop y otros articulos de fibra de vidrio	2026-01-09 12:52:15.476768-06	1
45206	Reparación de llantas de vehículos automotores	reparacion de llantas de vehiculos automotores	2026-01-09 12:52:15.476768-06	1
45207	Polarizado de vehículos (mediante la adhesión de papel especial a los vidrios)	polarizado de vehiculos (mediante la adhesion de papel especial a los vidrios)	2026-01-09 12:52:15.476768-06	1
45208	Lavado y pasteado de vehículos (carwash)	lavado y pasteado de vehiculos (carwash)	2026-01-09 12:52:15.476768-06	1
45209	Reparaciones de vehículos n.c.p.	reparaciones de vehiculos n.c.p.	2026-01-09 12:52:15.476768-06	1
45211	Remolque de vehículos automotores	remolque de vehiculos automotores	2026-01-09 12:52:15.476768-06	1
45301	Venta de partes, piezas y accesorios nuevos para vehículos automotores	venta de partes, piezas y accesorios nuevos para vehiculos automotores	2026-01-09 12:52:15.476768-06	1
45302	Venta de partes, piezas y accesorios usados para vehículos automotores	venta de partes, piezas y accesorios usados para vehiculos automotores	2026-01-09 12:52:15.476768-06	1
45401	Venta de motocicletas	venta de motocicletas	2026-01-09 12:52:15.476768-06	1
45402	Venta de repuestos, piezas y accesorios de motocicletas	venta de repuestos, piezas y accesorios de motocicletas	2026-01-09 12:52:15.476768-06	1
45403	Mantenimiento y reparación de motocicletas	mantenimiento y reparacion de motocicletas	2026-01-09 12:52:15.476768-06	1
46100	Venta al por mayor a cambio de retribución o por contrata	venta al por mayor a cambio de retribucion o por contrata	2026-01-09 12:52:15.476768-06	1
46201	Venta al por mayor de materias primas agrícolas	venta al por mayor de materias primas agricolas	2026-01-09 12:52:15.476768-06	1
46202	Venta al por mayor de productos de la silvicultura	venta al por mayor de productos de la silvicultura	2026-01-09 12:52:15.476768-06	1
46203	Venta al por mayor de productos pecuarios y de granja	venta al por mayor de productos pecuarios y de granja	2026-01-09 12:52:15.476768-06	1
46211	Venta de productos para uso agropecuario	venta de productos para uso agropecuario	2026-01-09 12:52:15.476768-06	1
46291	Venta al por mayor de granos básicos (cereales, leguminosas)	venta al por mayor de granos basicos (cereales, leguminosas)	2026-01-09 12:52:15.476768-06	1
46292	Venta al por mayor de semillas mejoradas para cultivo	venta al por mayor de semillas mejoradas para cultivo	2026-01-09 12:52:15.476768-06	1
46293	Venta al por mayor de café oro y uva	venta al por mayor de cafe oro y uva	2026-01-09 12:52:15.476768-06	1
46294	Venta al por mayor de caña de azúcar	venta al por mayor de cana de azucar	2026-01-09 12:52:15.476768-06	1
46295	Venta al por mayor de flores, plantas y otros productos naturales	venta al por mayor de flores, plantas y otros productos naturales	2026-01-09 12:52:15.476768-06	1
46296	Venta al por mayor de productos agrícolas	venta al por mayor de productos agricolas	2026-01-09 12:52:15.476768-06	1
46297	Venta al por mayor de ganado bovino (vivo)	venta al por mayor de ganado bovino (vivo)	2026-01-09 12:52:15.476768-06	1
46298	Venta al por mayor de animales porcinos, ovinos, caprino, canículas, apícolas, avícolas vivos	venta al por mayor de animales porcinos, ovinos, caprino, caniculas, apicolas, avicolas vivos	2026-01-09 12:52:15.476768-06	1
46299	Venta de otras especies vivas del reino animal	venta de otras especies vivas del reino animal	2026-01-09 12:52:15.476768-06	1
46301	Venta al por mayor de alimentos	venta al por mayor de alimentos	2026-01-09 12:52:15.476768-06	1
46302	Venta al por mayor de bebidas	venta al por mayor de bebidas	2026-01-09 12:52:15.476768-06	1
46303	Venta al por mayor de tabaco	venta al por mayor de tabaco	2026-01-09 12:52:15.476768-06	1
46371	Venta al por mayor de frutas, hortalizas (verduras), legumbres y tubérculos	venta al por mayor de frutas, hortalizas (verduras), legumbres y tuberculos	2026-01-09 12:52:15.476768-06	1
46372	Venta al por mayor de pollos, gallinas destazadas, pavos y otras aves	venta al por mayor de pollos, gallinas destazadas, pavos y otras aves	2026-01-09 12:52:15.476768-06	1
46373	Venta al por mayor de carne bovina y porcina, productos de carne y embutidos	venta al por mayor de carne bovina y porcina, productos de carne y embutidos	2026-01-09 12:52:15.476768-06	1
46374	Venta al por mayor de huevos	venta al por mayor de huevos	2026-01-09 12:52:15.476768-06	1
46376	Venta al por mayor de productos farináceos de panadería (pan dulce, cakes, respostería, etc.)	venta al por mayor de productos farinaceos de panaderia (pan dulce, cakes, resposteria, etc.)	2026-01-09 12:52:15.476768-06	1
46377	Venta al por mayor de pastas alimenticias, aceites y grasas comestibles vegetal y animal	venta al por mayor de pastas alimenticias, aceites y grasas comestibles vegetal y animal	2026-01-09 12:52:15.476768-06	1
46378	Venta al por mayor de sal comestible	venta al por mayor de sal comestible	2026-01-09 12:52:15.476768-06	1
46379	Venta al por mayor de azúcar	venta al por mayor de azucar	2026-01-09 12:52:15.476768-06	1
46391	Venta al por mayor de abarrotes (vinos, licores, productos alimenticios envasados, etc.)	venta al por mayor de abarrotes (vinos, licores, productos alimenticios envasados, etc.)	2026-01-09 12:52:15.476768-06	1
46392	Venta al por mayor de aguas gaseosas	venta al por mayor de aguas gaseosas	2026-01-09 12:52:15.476768-06	1
46393	Venta al por mayor de agua purificada	venta al por mayor de agua purificada	2026-01-09 12:52:15.476768-06	1
46394	Venta al por mayor de refrescos y otras bebidas, líquidas o en polvo	venta al por mayor de refrescos y otras bebidas, liquidas o en polvo	2026-01-09 12:52:15.476768-06	1
46395	Venta al por mayor de cerveza y licores	venta al por mayor de cerveza y licores	2026-01-09 12:52:15.476768-06	1
46396	Venta al por mayor de hielo	venta al por mayor de hielo	2026-01-09 12:52:15.476768-06	1
46411	Venta al por mayor de hilados, tejidos y productos textiles de mercería	venta al por mayor de hilados, tejidos y productos textiles de merceria	2026-01-09 12:52:15.476768-06	1
46412	Venta al por mayor de artículos textiles excepto confecciones para el hogar	venta al por mayor de articulos textiles excepto confecciones para el hogar	2026-01-09 12:52:15.476768-06	1
46413	Venta al por mayor de confecciones textiles para el hogar	venta al por mayor de confecciones textiles para el hogar	2026-01-09 12:52:15.476768-06	1
46414	Venta al por mayor de prendas de vestir y accesorios de vestir	venta al por mayor de prendas de vestir y accesorios de vestir	2026-01-09 12:52:15.476768-06	1
46415	Venta al por mayor de ropa usada	venta al por mayor de ropa usada	2026-01-09 12:52:15.476768-06	1
46416	Venta al por mayor de calzado	venta al por mayor de calzado	2026-01-09 12:52:15.476768-06	1
46417	Venta al por mayor de artículos de marroquinería y talabartería	venta al por mayor de articulos de marroquineria y talabarteria	2026-01-09 12:52:15.476768-06	1
46418	Venta al por mayor de artículos de peletería	venta al por mayor de articulos de peleteria	2026-01-09 12:52:15.476768-06	1
46419	Venta al por mayor de otros artículos textiles n.c.p.	venta al por mayor de otros articulos textiles n.c.p.	2026-01-09 12:52:15.476768-06	1
46471	Venta al por mayor de instrumentos musicales	venta al por mayor de instrumentos musicales	2026-01-09 12:52:15.476768-06	1
46472	Venta al por mayor de colchones, almohadas, cojines, etc.	venta al por mayor de colchones, almohadas, cojines, etc.	2026-01-09 12:52:15.476768-06	1
46473	Venta al por mayor de artículos de aluminio para el hogar y para otros usos	venta al por mayor de articulos de aluminio para el hogar y para otros usos	2026-01-09 12:52:15.476768-06	1
46474	Venta al por mayor de depósitos y otros artículos plásticos para el hogar y otros usos, incluyendo los desechables de durapax y no desechables	venta al por mayor de depositos y otros articulos plasticos para el hogar y otros usos, incluyendo los desechables de durapax y no desechables	2026-01-09 12:52:15.476768-06	1
46475	Venta al por mayor de cámaras fotográficas, accesorios y materiales	venta al por mayor de camaras fotograficas, accesorios y materiales	2026-01-09 12:52:15.476768-06	1
46482	Venta al por mayor de medicamentos, artículos y otros productos de uso veterinario	venta al por mayor de medicamentos, articulos y otros productos de uso veterinario	2026-01-09 12:52:15.476768-06	1
46483	Venta al por mayor de productos y artículos de belleza y de uso personal	venta al por mayor de productos y articulos de belleza y de uso personal	2026-01-09 12:52:15.476768-06	1
46484	Venta de productos farmacéuticos y medicinales	venta de productos farmaceuticos y medicinales	2026-01-09 12:52:15.476768-06	1
46491	Venta al por mayor de productos medicinales, cosméticos, perfumería y productos de limpieza	venta al por mayor de productos medicinales, cosmeticos, perfumeria y productos de limpieza	2026-01-09 12:52:15.476768-06	1
46492	Venta al por mayor de relojes y artículos de joyería	venta al por mayor de relojes y articulos de joyeria	2026-01-09 12:52:15.476768-06	1
46493	Venta al por mayor de electrodomésticos y artículos del hogar excepto bazar; artículos de iluminación	venta al por mayor de electrodomesticos y articulos del hogar excepto bazar; articulos de iluminacion	2026-01-09 12:52:15.476768-06	1
46494	Venta al por mayor de artículos de bazar y similares	venta al por mayor de articulos de bazar y similares	2026-01-09 12:52:15.476768-06	1
46495	Venta al por mayor de artículos de óptica	venta al por mayor de articulos de optica	2026-01-09 12:52:15.476768-06	1
46496	Venta al por mayor de revistas, periódicos, libros, artículos de librería y artículos de papel y cartón en general	venta al por mayor de revistas, periodicos, libros, articulos de libreria y articulos de papel y carton en general	2026-01-09 12:52:15.476768-06	1
46497	Venta de artículos deportivos, juguetes y rodados	venta de articulos deportivos, juguetes y rodados	2026-01-09 12:52:15.476768-06	1
46498	Venta al por mayor de productos usados para el hogar o el uso personal	venta al por mayor de productos usados para el hogar o el uso personal	2026-01-09 12:52:15.476768-06	1
46499	Venta al por mayor de enseres domésticos y de uso personal n.c.p.	venta al por mayor de enseres domesticos y de uso personal n.c.p.	2026-01-09 12:52:15.476768-06	1
46500	Venta al por mayor de bicicletas, partes, accesorios y otros	venta al por mayor de bicicletas, partes, accesorios y otros	2026-01-09 12:52:15.476768-06	1
46510	Venta al por mayor de computadoras, equipo periférico y programas informáticos	venta al por mayor de computadoras, equipo periferico y programas informaticos	2026-01-09 12:52:15.476768-06	1
46520	Venta al por mayor de equipos de comunicación	venta al por mayor de equipos de comunicacion	2026-01-09 12:52:15.476768-06	1
46530	Venta al por mayor de maquinaria y equipo agropecuario, accesorios, partes y suministros	venta al por mayor de maquinaria y equipo agropecuario, accesorios, partes y suministros	2026-01-09 12:52:15.476768-06	1
46590	Venta de equipos e instrumentos de uso profesional y científico y aparatos de medida y control	venta de equipos e instrumentos de uso profesional y cientifico y aparatos de medida y control	2026-01-09 12:52:15.476768-06	1
46591	Venta al por mayor de maquinaria equipo, accesorios y materiales para la industria de la madera y sus productos	venta al por mayor de maquinaria equipo, accesorios y materiales para la industria de la madera y sus productos	2026-01-09 12:52:15.476768-06	1
47199	Venta de establecimientos no especializados con surtido compuesto principalmente de alimentos, bebidas y tabaco	venta de establecimientos no especializados con surtido compuesto principalmente de alimentos, bebidas y tabaco	2026-01-09 12:52:15.476768-06	1
46592	Venta al por mayor de maquinaria, equipo, accesorios y materiales para la industria gráfica y del papel, cartón y productos de papel y cartón	venta al por mayor de maquinaria, equipo, accesorios y materiales para la industria grafica y del papel, carton y productos de papel y carton	2026-01-09 12:52:15.476768-06	1
47739	Venta al por menor de otros productos n.c.p.	venta al por menor de otros productos n.c.p.	2026-01-09 12:52:15.476768-06	1
46593	Venta al por mayor de maquinaria, equipo, accesorios y materiales para la industria de productos químicos, plástico y caucho	venta al por mayor de maquinaria, equipo, accesorios y materiales para la industria de productos quimicos, plastico y caucho	2026-01-09 12:52:15.476768-06	1
46594	Venta al por mayor de maquinaria, equipo, accesorios y materiales para la industria metálica y de sus productos	venta al por mayor de maquinaria, equipo, accesorios y materiales para la industria metalica y de sus productos	2026-01-09 12:52:15.476768-06	1
46595	Venta al por mayor de equipamiento para uso médico, odontológico, veterinario y servicios conexos	venta al por mayor de equipamiento para uso medico, odontologico, veterinario y servicios conexos	2026-01-09 12:52:15.476768-06	1
46596	Venta al por mayor de maquinaria, equipo, accesorios y partes para la industria de la alimentación	venta al por mayor de maquinaria, equipo, accesorios y partes para la industria de la alimentacion	2026-01-09 12:52:15.476768-06	1
46597	Venta al por mayor de maquinaria, equipo, accesorios y partes para la industria textil, confecciones y cuero	venta al por mayor de maquinaria, equipo, accesorios y partes para la industria textil, confecciones y cuero	2026-01-09 12:52:15.476768-06	1
46598	Venta al por mayor de maquinaria, equipo y accesorios para la construcción y explotación de minas y canteras	venta al por mayor de maquinaria, equipo y accesorios para la construccion y explotacion de minas y canteras	2026-01-09 12:52:15.476768-06	1
46599	Venta al por mayor de otro tipo de maquinaria y equipo con sus accesorios y partes	venta al por mayor de otro tipo de maquinaria y equipo con sus accesorios y partes	2026-01-09 12:52:15.476768-06	1
46610	Venta al por mayor de otros combustibles sólidos, líquidos, gaseosos y de productos conexos	venta al por mayor de otros combustibles solidos, liquidos, gaseosos y de productos conexos	2026-01-09 12:52:15.476768-06	1
46612	Venta al por mayor de combustibles para automotores, aviones, barcos, maquinaria y otros	venta al por mayor de combustibles para automotores, aviones, barcos, maquinaria y otros	2026-01-09 12:52:15.476768-06	1
46613	Venta al por mayor de lubricantes, grasas y otros aceites para automotores, maquinaria industrial, etc.	venta al por mayor de lubricantes, grasas y otros aceites para automotores, maquinaria industrial, etc.	2026-01-09 12:52:15.476768-06	1
46614	Venta al por mayor de gas propano	venta al por mayor de gas propano	2026-01-09 12:52:15.476768-06	1
46615	Venta al por mayor de leña y carbón	venta al por mayor de lena y carbon	2026-01-09 12:52:15.476768-06	1
46620	Venta al por mayor de metales y minerales metalíferos	venta al por mayor de metales y minerales metaliferos	2026-01-09 12:52:15.476768-06	1
46631	Venta al por mayor de puertas, ventanas, vitrinas y similares	venta al por mayor de puertas, ventanas, vitrinas y similares	2026-01-09 12:52:15.476768-06	1
46632	Venta al por mayor de artículos de ferretería y pinturerías	venta al por mayor de articulos de ferreteria y pinturerias	2026-01-09 12:52:15.476768-06	1
46633	Vidrierías	vidrierias	2026-01-09 12:52:15.476768-06	1
46634	Venta al por mayor de maderas	venta al por mayor de maderas	2026-01-09 12:52:15.476768-06	1
46639	Venta al por mayor de materiales para la construcción n.c.p.	venta al por mayor de materiales para la construccion n.c.p.	2026-01-09 12:52:15.476768-06	1
46691	Venta al por mayor de sal industrial sin yodar	venta al por mayor de sal industrial sin yodar	2026-01-09 12:52:15.476768-06	1
46692	Venta al por mayor de productos intermedios y desechos de origen textil	venta al por mayor de productos intermedios y desechos de origen textil	2026-01-09 12:52:15.476768-06	1
46693	Venta al por mayor de productos intermedios y desechos de origen metálico	venta al por mayor de productos intermedios y desechos de origen metalico	2026-01-09 12:52:15.476768-06	1
46694	Venta al por mayor de productos intermedios y desechos de papel y cartón	venta al por mayor de productos intermedios y desechos de papel y carton	2026-01-09 12:52:15.476768-06	1
46695	Venta al por mayor fertilizantes, abonos, agroquímicos y productos similares	venta al por mayor fertilizantes, abonos, agroquimicos y productos similares	2026-01-09 12:52:15.476768-06	1
46696	Venta al por mayor de productos intermedios y desechos de origen plástico	venta al por mayor de productos intermedios y desechos de origen plastico	2026-01-09 12:52:15.476768-06	1
46697	Venta al por mayor de tintas para imprenta, productos curtientes y materias y productos colorantes	venta al por mayor de tintas para imprenta, productos curtientes y materias y productos colorantes	2026-01-09 12:52:15.476768-06	1
46698	Venta de productos intermedios y desechos de origen químico y de caucho	venta de productos intermedios y desechos de origen quimico y de caucho	2026-01-09 12:52:15.476768-06	1
46699	Venta al por mayor de productos intermedios y desechos ncp	venta al por mayor de productos intermedios y desechos ncp	2026-01-09 12:52:15.476768-06	1
46701	Venta de algodón en oro	venta de algodon en oro	2026-01-09 12:52:15.476768-06	1
46900	Venta al por mayor de otros productos	venta al por mayor de otros productos	2026-01-09 12:52:15.476768-06	1
46901	Venta al por mayor de cohetes y otros productos pirotécnicos	venta al por mayor de cohetes y otros productos pirotecnicos	2026-01-09 12:52:15.476768-06	1
46902	Venta al por mayor de artículos diversos para consumo humano	venta al por mayor de articulos diversos para consumo humano	2026-01-09 12:52:15.476768-06	1
46903	Venta al por mayor de armas de fuego, municiones y accesorios	venta al por mayor de armas de fuego, municiones y accesorios	2026-01-09 12:52:15.476768-06	1
46904	Venta al por mayor de toldos y tiendas de campaña de cualquier material	venta al por mayor de toldos y tiendas de campana de cualquier material	2026-01-09 12:52:15.476768-06	1
46905	Venta al por mayor de exhibidores publicitarios y rótulos	venta al por mayor de exhibidores publicitarios y rotulos	2026-01-09 12:52:15.476768-06	1
46906	Venta al por mayor de artículos promocionales diversos	venta al por mayor de articulos promocionales diversos	2026-01-09 12:52:15.476768-06	1
47111	Venta en supermercados	venta en supermercados	2026-01-09 12:52:15.476768-06	1
47112	Venta en tiendas de artículos de primera necesidad	venta en tiendas de articulos de primera necesidad	2026-01-09 12:52:15.476768-06	1
47119	Almacenes (venta de diversos artículos)	almacenes (venta de diversos articulos)	2026-01-09 12:52:15.476768-06	1
47120	Almacenes (venta de diversos artículos), y venta de vehículos automotores y motocicletas	almacenes (venta de diversos articulos), y venta de vehiculos automotores y motocicletas	2026-01-09 12:52:15.476768-06	1
47190	Venta al por menor de otros productos en comercios no especializados	venta al por menor de otros productos en comercios no especializados	2026-01-09 12:52:15.476768-06	1
47211	Venta al por menor de frutas y hortalizas	venta al por menor de frutas y hortalizas	2026-01-09 12:52:15.476768-06	1
47212	Venta al por menor de carnes, embutidos y productos de granja	venta al por menor de carnes, embutidos y productos de granja	2026-01-09 12:52:15.476768-06	1
47213	Venta al por menor de pescado y mariscos	venta al por menor de pescado y mariscos	2026-01-09 12:52:15.476768-06	1
47214	Venta al por menor de productos lácteos	venta al por menor de productos lacteos	2026-01-09 12:52:15.476768-06	1
47215	Venta al por menor de productos de panadería, repostería y galletas	venta al por menor de productos de panaderia, reposteria y galletas	2026-01-09 12:52:15.476768-06	1
47216	Venta al por menor de huevos	venta al por menor de huevos	2026-01-09 12:52:15.476768-06	1
47217	Venta al por menor de carnes y productos cárnicos	venta al por menor de carnes y productos carnicos	2026-01-09 12:52:15.476768-06	1
47218	Venta al por menor de granos básicos y otros	venta al por menor de granos basicos y otros	2026-01-09 12:52:15.476768-06	1
47219	Venta al por menor de alimentos n.c.p.	venta al por menor de alimentos n.c.p.	2026-01-09 12:52:15.476768-06	1
47221	Venta al por menor de hielo	venta al por menor de hielo	2026-01-09 12:52:15.476768-06	1
47223	Venta de bebidas no alcohólicas, para su consumo fuera del establecimiento	venta de bebidas no alcoholicas, para su consumo fuera del establecimiento	2026-01-09 12:52:15.476768-06	1
47224	Venta de bebidas alcohólicas, para su consumo fuera del establecimiento	venta de bebidas alcoholicas, para su consumo fuera del establecimiento	2026-01-09 12:52:15.476768-06	1
47225	Venta de bebidas alcohólicas para su consumo dentro del establecimiento	venta de bebidas alcoholicas para su consumo dentro del establecimiento	2026-01-09 12:52:15.476768-06	1
47230	Venta al por menor de tabaco	venta al por menor de tabaco	2026-01-09 12:52:15.476768-06	1
47300	Venta de combustibles, lubricantes y otros (gasolineras)	venta de combustibles, lubricantes y otros (gasolineras)	2026-01-09 12:52:15.476768-06	1
47411	Venta al por menor de computadoras y equipo periférico	venta al por menor de computadoras y equipo periferico	2026-01-09 12:52:15.476768-06	1
47412	Venta de equipo y accesorios de telecomunicación	venta de equipo y accesorios de telecomunicacion	2026-01-09 12:52:15.476768-06	1
47420	Venta al por menor de equipo de audio y video	venta al por menor de equipo de audio y video	2026-01-09 12:52:15.476768-06	1
47510	Venta al por menor de hilados, tejidos y productos textiles de mercería; confecciones para el hogar y textiles n.c.p.	venta al por menor de hilados, tejidos y productos textiles de merceria; confecciones para el hogar y textiles n.c.p.	2026-01-09 12:52:15.476768-06	1
47521	Venta al por menor de productos de madera	venta al por menor de productos de madera	2026-01-09 12:52:15.476768-06	1
47522	Venta al por menor de artículos de ferretería	venta al por menor de articulos de ferreteria	2026-01-09 12:52:15.476768-06	1
47523	Venta al por menor de productos de pinturerías	venta al por menor de productos de pinturerias	2026-01-09 12:52:15.476768-06	1
47524	Venta al por menor en vidrierías	venta al por menor en vidrierias	2026-01-09 12:52:15.476768-06	1
47529	Venta al por menor de materiales de construcción y artículos conexos	venta al por menor de materiales de construccion y articulos conexos	2026-01-09 12:52:15.476768-06	1
47530	Venta al por menor de tapices, alfombras y revestimientos de paredes y pisos en comercios especializados	venta al por menor de tapices, alfombras y revestimientos de paredes y pisos en comercios especializados	2026-01-09 12:52:15.476768-06	1
47591	Venta al por menor de muebles	venta al por menor de muebles	2026-01-09 12:52:15.476768-06	1
47592	Venta al por menor de artículos de bazar	venta al por menor de articulos de bazar	2026-01-09 12:52:15.476768-06	1
47593	Venta al por menor de aparatos electrodomésticos, repuestos y accesorios	venta al por menor de aparatos electrodomesticos, repuestos y accesorios	2026-01-09 12:52:15.476768-06	1
47594	Venta al por menor de artículos eléctricos y de iluminación	venta al por menor de articulos electricos y de iluminacion	2026-01-09 12:52:15.476768-06	1
47598	Venta al por menor de instrumentos musicales	venta al por menor de instrumentos musicales	2026-01-09 12:52:15.476768-06	1
47610	Venta al por menor de libros, periódicos y artículos de papelería en comercios especializados	venta al por menor de libros, periodicos y articulos de papeleria en comercios especializados	2026-01-09 12:52:15.476768-06	1
47620	Venta al por menor de discos láser, cassettes, cintas de video y otros	venta al por menor de discos laser, cassettes, cintas de video y otros	2026-01-09 12:52:15.476768-06	1
47630	Venta al por menor de productos y equipos de deporte	venta al por menor de productos y equipos de deporte	2026-01-09 12:52:15.476768-06	1
47631	Venta al por menor de bicicletas, accesorios y repuestos	venta al por menor de bicicletas, accesorios y repuestos	2026-01-09 12:52:15.476768-06	1
47640	Venta al por menor de juegos y juguetes en comercios especializados	venta al por menor de juegos y juguetes en comercios especializados	2026-01-09 12:52:15.476768-06	1
47711	Venta al por menor de prendas de vestir y accesorios de vestir	venta al por menor de prendas de vestir y accesorios de vestir	2026-01-09 12:52:15.476768-06	1
47712	Venta al por menor de calzado	venta al por menor de calzado	2026-01-09 12:52:15.476768-06	1
47713	Venta al por menor de artículos de peletería, marroquinería y talabartería	venta al por menor de articulos de peleteria, marroquineria y talabarteria	2026-01-09 12:52:15.476768-06	1
47721	Venta al por menor de medicamentos farmacéuticos y otros materiales y artículos de uso médico, odontológico y veterinario	venta al por menor de medicamentos farmaceuticos y otros materiales y articulos de uso medico, odontologico y veterinario	2026-01-09 12:52:15.476768-06	1
47722	Venta al por menor de productos cosméticos y de tocador	venta al por menor de productos cosmeticos y de tocador	2026-01-09 12:52:15.476768-06	1
47731	Venta al por menor de productos de joyería, bisutería, óptica, relojería	venta al por menor de productos de joyeria, bisuteria, optica, relojeria	2026-01-09 12:52:15.476768-06	1
47732	Venta al por menor de plantas, semillas, animales y artículos conexos	venta al por menor de plantas, semillas, animales y articulos conexos	2026-01-09 12:52:15.476768-06	1
47733	Venta al por menor de combustibles de uso doméstico (gas propano y gas licuado)	venta al por menor de combustibles de uso domestico (gas propano y gas licuado)	2026-01-09 12:52:15.476768-06	1
47734	Venta al por menor de artesanías, artículos cerámicos y recuerdos en general	venta al por menor de artesanias, articulos ceramicos y recuerdos en general	2026-01-09 12:52:15.476768-06	1
47735	Venta al por menor de ataúdes, lápidas y cruces, trofeos, artículos religiosos en general	venta al por menor de ataudes, lapidas y cruces, trofeos, articulos religiosos en general	2026-01-09 12:52:15.476768-06	1
47736	Venta al por menor de armas de fuego, municiones y accesorios	venta al por menor de armas de fuego, municiones y accesorios	2026-01-09 12:52:15.476768-06	1
47737	Venta al por menor de artículos de cohetería y pirotécnicos	venta al por menor de articulos de coheteria y pirotecnicos	2026-01-09 12:52:15.476768-06	1
47738	Venta al por menor de artículos desechables de uso personal y doméstico (servilletas, papel higiénico, pañales, toallas sanitarias, etc.)	venta al por menor de articulos desechables de uso personal y domestico (servilletas, papel higienico, panales, toallas sanitarias, etc.)	2026-01-09 12:52:15.476768-06	1
47741	Venta al por menor de artículos usados	venta al por menor de articulos usados	2026-01-09 12:52:15.476768-06	1
47742	Venta al por menor de textiles y confecciones usados	venta al por menor de textiles y confecciones usados	2026-01-09 12:52:15.476768-06	1
47743	Venta al por menor de libros, revistas, papel y cartón usados	venta al por menor de libros, revistas, papel y carton usados	2026-01-09 12:52:15.476768-06	1
47749	Venta al por menor de productos usados n.c.p.	venta al por menor de productos usados n.c.p.	2026-01-09 12:52:15.476768-06	1
47811	Venta al por menor de frutas, verduras y hortalizas	venta al por menor de frutas, verduras y hortalizas	2026-01-09 12:52:15.476768-06	1
47814	Venta al por menor de productos lácteos	venta al por menor de productos lacteos	2026-01-09 12:52:15.476768-06	1
47815	Venta al por menor de productos de panadería, galletas y similares	venta al por menor de productos de panaderia, galletas y similares	2026-01-09 12:52:15.476768-06	1
47816	Venta al por menor de bebidas	venta al por menor de bebidas	2026-01-09 12:52:15.476768-06	1
47818	Venta al por menor en tiendas de mercado y puestos	venta al por menor en tiendas de mercado y puestos	2026-01-09 12:52:15.476768-06	1
47821	Venta al por menor de hilados, tejidos y productos textiles de mercería en puestos de mercados y ferias	venta al por menor de hilados, tejidos y productos textiles de merceria en puestos de mercados y ferias	2026-01-09 12:52:15.476768-06	1
47822	Venta al por menor de artículos textiles excepto confecciones para el hogar en puestos de mercados y ferias	venta al por menor de articulos textiles excepto confecciones para el hogar en puestos de mercados y ferias	2026-01-09 12:52:15.476768-06	1
47823	Venta al por menor de confecciones textiles para el hogar en puestos de mercados y ferias	venta al por menor de confecciones textiles para el hogar en puestos de mercados y ferias	2026-01-09 12:52:15.476768-06	1
47824	Venta al por menor de prendas de vestir, accesorios de vestir y similares en puestos de mercados y ferias	venta al por menor de prendas de vestir, accesorios de vestir y similares en puestos de mercados y ferias	2026-01-09 12:52:15.476768-06	1
47825	Venta al por menor de ropa usada	venta al por menor de ropa usada	2026-01-09 12:52:15.476768-06	1
47826	Venta al por menor de calzado, artículos de marroquinería y talabartería en puestos de mercados y ferias	venta al por menor de calzado, articulos de marroquineria y talabarteria en puestos de mercados y ferias	2026-01-09 12:52:15.476768-06	1
47827	Venta al por menor de artículos de marroquinería y talabartería en puestos de mercados y ferias	venta al por menor de articulos de marroquineria y talabarteria en puestos de mercados y ferias	2026-01-09 12:52:15.476768-06	1
47829	Venta al por menor de artículos textiles ncp en puestos de mercados y ferias	venta al por menor de articulos textiles ncp en puestos de mercados y ferias	2026-01-09 12:52:15.476768-06	1
47891	Venta al por menor de animales, flores y productos conexos en puestos de feria y mercados	venta al por menor de animales, flores y productos conexos en puestos de feria y mercados	2026-01-09 12:52:15.476768-06	1
47892	Venta al por menor de productos medicinales, cosméticos, de tocador y de limpieza en puestos de ferias y mercados	venta al por menor de productos medicinales, cosmeticos, de tocador y de limpieza en puestos de ferias y mercados	2026-01-09 12:52:15.476768-06	1
47893	Venta al por menor de artículos de bazar en puestos de ferias y mercados	venta al por menor de articulos de bazar en puestos de ferias y mercados	2026-01-09 12:52:15.476768-06	1
47894	Venta al por menor de artículos de papel, envases, libros, revistas y conexos en puestos de feria y mercados	venta al por menor de articulos de papel, envases, libros, revistas y conexos en puestos de feria y mercados	2026-01-09 12:52:15.476768-06	1
47895	Venta al por menor de materiales de construcción, electrodomésticos, accesorios para autos y similares en puestos de feria y mercados	venta al por menor de materiales de construccion, electrodomesticos, accesorios para autos y similares en puestos de feria y mercados	2026-01-09 12:52:15.476768-06	1
47896	Venta al por menor de equipos accesorios para las comunicaciones en puestos de feria y mercados	venta al por menor de equipos accesorios para las comunicaciones en puestos de feria y mercados	2026-01-09 12:52:15.476768-06	1
47899	Venta al por menor en puestos de ferias y mercados n.c.p.	venta al por menor en puestos de ferias y mercados n.c.p.	2026-01-09 12:52:15.476768-06	1
47910	Venta al por menor por correo o Internet	venta al por menor por correo o internet	2026-01-09 12:52:15.476768-06	1
47990	Otros tipos de venta al por menor no realizada, en almacenes, puestos de venta o mercado	otros tipos de venta al por menor no realizada, en almacenes, puestos de venta o mercado	2026-01-09 12:52:15.476768-06	1
49110	Transporte interurbano de pasajeros por ferrocarril	transporte interurbano de pasajeros por ferrocarril	2026-01-09 12:52:15.476768-06	1
49120	Transporte de carga por ferrocarril	transporte de carga por ferrocarril	2026-01-09 12:52:15.476768-06	1
49211	Transporte de pasajeros urbanos e interurbano mediante buses	transporte de pasajeros urbanos e interurbano mediante buses	2026-01-09 12:52:15.476768-06	1
49212	Transporte de pasajeros interdepartamental mediante microbuses	transporte de pasajeros interdepartamental mediante microbuses	2026-01-09 12:52:15.476768-06	1
49213	Transporte de pasajeros urbanos e interurbano mediante microbuses	transporte de pasajeros urbanos e interurbano mediante microbuses	2026-01-09 12:52:15.476768-06	1
49214	Transporte de pasajeros interdepartamental mediante buses	transporte de pasajeros interdepartamental mediante buses	2026-01-09 12:52:15.476768-06	1
49221	Transporte internacional de pasajeros	transporte internacional de pasajeros	2026-01-09 12:52:15.476768-06	1
49222	Transporte de pasajeros mediante taxis y autos con chofer	transporte de pasajeros mediante taxis y autos con chofer	2026-01-09 12:52:15.476768-06	1
49223	Transporte escolar	transporte escolar	2026-01-09 12:52:15.476768-06	1
49225	Transporte de pasajeros para excursiones	transporte de pasajeros para excursiones	2026-01-09 12:52:15.476768-06	1
49226	Servicios de transporte de personal	servicios de transporte de personal	2026-01-09 12:52:15.476768-06	1
49229	Transporte de pasajeros por vía terrestre ncp	transporte de pasajeros por via terrestre ncp	2026-01-09 12:52:15.476768-06	1
49231	Transporte de carga urbano	transporte de carga urbano	2026-01-09 12:52:15.476768-06	1
49232	Transporte nacional de carga	transporte nacional de carga	2026-01-09 12:52:15.476768-06	1
49233	Transporte de carga internacional	transporte de carga internacional	2026-01-09 12:52:15.476768-06	1
49234	Servicios de mudanza	servicios de mudanza	2026-01-09 12:52:15.476768-06	1
49235	Alquiler de vehículos de carga con conductor	alquiler de vehiculos de carga con conductor	2026-01-09 12:52:15.476768-06	1
49300	Transporte por oleoducto o gasoducto\\	transporte por oleoducto o gasoducto\\	2026-01-09 12:52:15.476768-06	1
50110	Transporte de pasajeros marítimo y de cabotaje	transporte de pasajeros maritimo y de cabotaje	2026-01-09 12:52:15.476768-06	1
50120	Transporte de carga marítimo y de cabotaje	transporte de carga maritimo y de cabotaje	2026-01-09 12:52:15.476768-06	1
50211	Transporte de pasajeros por vías de navegación interiores	transporte de pasajeros por vias de navegacion interiores	2026-01-09 12:52:15.476768-06	1
50212	Alquiler de equipo de transporte de pasajeros por vías de navegación interior con conductor	alquiler de equipo de transporte de pasajeros por vias de navegacion interior con conductor	2026-01-09 12:52:15.476768-06	1
50220	Transporte de carga por vías de navegación interiores	transporte de carga por vias de navegacion interiores	2026-01-09 12:52:15.476768-06	1
51100	Transporte aéreo de pasajeros	transporte aereo de pasajeros	2026-01-09 12:52:15.476768-06	1
51201	Transporte de carga por vía aérea	transporte de carga por via aerea	2026-01-09 12:52:15.476768-06	1
51202	Alquiler de equipo de aerotransporte con operadores para el propósito de transportar carga	alquiler de equipo de aerotransporte con operadores para el proposito de transportar carga	2026-01-09 12:52:15.476768-06	1
52101	Alquiler de instalaciones de almacenamiento en zonas francas	alquiler de instalaciones de almacenamiento en zonas francas	2026-01-09 12:52:15.476768-06	1
52102	Alquiler de silos para conservación y almacenamiento de granos	alquiler de silos para conservacion y almacenamiento de granos	2026-01-09 12:52:15.476768-06	1
52103	Alquiler de instalaciones con refrigeración para almacenamiento y conservación de alimentos y otros productos	alquiler de instalaciones con refrigeracion para almacenamiento y conservacion de alimentos y otros productos	2026-01-09 12:52:15.476768-06	1
52109	Alquiler de bodegas para almacenamiento y depósito n.c.p.	alquiler de bodegas para almacenamiento y deposito n.c.p.	2026-01-09 12:52:15.476768-06	1
52211	Servicio de garaje y estacionamiento	servicio de garaje y estacionamiento	2026-01-09 12:52:15.476768-06	1
52212	Servicios de terminales para el transporte por vía terrestre	servicios de terminales para el transporte por via terrestre	2026-01-09 12:52:15.476768-06	1
52219	Servicios para el transporte por vía terrestre n.c.p.	servicios para el transporte por via terrestre n.c.p.	2026-01-09 12:52:15.476768-06	1
52220	Servicios para el transporte acuático	servicios para el transporte acuatico	2026-01-09 12:52:15.476768-06	1
52230	Servicios para el transporte aéreo	servicios para el transporte aereo	2026-01-09 12:52:15.476768-06	1
52240	Manipulación de carga	manipulacion de carga	2026-01-09 12:52:15.476768-06	1
52290	Servicios para el transporte ncp	servicios para el transporte ncp	2026-01-09 12:52:15.476768-06	1
52291	Agencias de tramitaciones aduanales	agencias de tramitaciones aduanales	2026-01-09 12:52:15.476768-06	1
53100	Servicios de correo nacional	servicios de correo nacional	2026-01-09 12:52:15.476768-06	1
53200	Actividades de correo distintas a las actividades postales nacionales	actividades de correo distintas a las actividades postales nacionales	2026-01-09 12:52:15.476768-06	1
53201	Agencia privada de correo y encomiendas	agencia privada de correo y encomiendas	2026-01-09 12:52:15.476768-06	1
55101	Actividades de alojamiento para estancias cortas	actividades de alojamiento para estancias cortas	2026-01-09 12:52:15.476768-06	1
55102	Hoteles	hoteles	2026-01-09 12:52:15.476768-06	1
55200	Actividades de campamentos, parques de vehículos de recreo y parques de caravanas	actividades de campamentos, parques de vehiculos de recreo y parques de caravanas	2026-01-09 12:52:15.476768-06	1
55900	Alojamiento n.c.p.	alojamiento n.c.p.	2026-01-09 12:52:15.476768-06	1
56101	Restaurantes	restaurantes	2026-01-09 12:52:15.476768-06	1
56106	Pupusería	pupuseria	2026-01-09 12:52:15.476768-06	1
56107	Actividades varias de restaurantes	actividades varias de restaurantes	2026-01-09 12:52:15.476768-06	1
56108	Comedores	comedores	2026-01-09 12:52:15.476768-06	1
56109	Merenderos ambulantes	merenderos ambulantes	2026-01-09 12:52:15.476768-06	1
56210	Preparación de comida para eventos especiales	preparacion de comida para eventos especiales	2026-01-09 12:52:15.476768-06	1
56291	Servicios de provisión de comidas por contrato	servicios de provision de comidas por contrato	2026-01-09 12:52:15.476768-06	1
56292	Servicios de concesión de cafetines y chalet en empresas e instituciones	servicios de concesion de cafetines y chalet en empresas e instituciones	2026-01-09 12:52:15.476768-06	1
56299	Servicios de preparación de comidas ncp	servicios de preparacion de comidas ncp	2026-01-09 12:52:15.476768-06	1
56301	Servicio de expendio de bebidas en salones y bares	servicio de expendio de bebidas en salones y bares	2026-01-09 12:52:15.476768-06	1
56302	Servicio de expendio de bebidas en puestos callejeros, mercados y ferias	servicio de expendio de bebidas en puestos callejeros, mercados y ferias	2026-01-09 12:52:15.476768-06	1
58110	Edición de libros, folletos, partituras y otras ediciones distintas a estas	edicion de libros, folletos, partituras y otras ediciones distintas a estas	2026-01-09 12:52:15.476768-06	1
58120	Edición de directorios y listas de correos	edicion de directorios y listas de correos	2026-01-09 12:52:15.476768-06	1
58130	Edición de periódicos, revistas y otras publicaciones periódicas	edicion de periodicos, revistas y otras publicaciones periodicas	2026-01-09 12:52:15.476768-06	1
58190	Otras actividades de edición	otras actividades de edicion	2026-01-09 12:52:15.476768-06	1
58200	Edición de programas informáticos (software)	edicion de programas informaticos (software)	2026-01-09 12:52:15.476768-06	1
59110	Actividades de producción cinematográfica	actividades de produccion cinematografica	2026-01-09 12:52:15.476768-06	1
59120	Actividades de post producción de películas, videos y programas de televisión	actividades de post produccion de peliculas, videos y programas de television	2026-01-09 12:52:15.476768-06	1
59130	Actividades de distribución de películas cinematográficas, videos y programas de televisión	actividades de distribucion de peliculas cinematograficas, videos y programas de television	2026-01-09 12:52:15.476768-06	1
59140	Actividades de exhibición de películas cinematográficas y cintas de vídeo	actividades de exhibicion de peliculas cinematograficas y cintas de video	2026-01-09 12:52:15.476768-06	1
59200	Actividades de edición y grabación de música	actividades de edicion y grabacion de musica	2026-01-09 12:52:15.476768-06	1
60100	Servicios de difusiones de radio	servicios de difusiones de radio	2026-01-09 12:52:15.476768-06	1
60201	Actividades de programación y difusión de televisión abierta	actividades de programacion y difusion de television abierta	2026-01-09 12:52:15.476768-06	1
60202	Actividades de suscripción y difusión de televisión por cable y/o suscripción	actividades de suscripcion y difusion de television por cable y/o suscripcion	2026-01-09 12:52:15.476768-06	1
60299	Servicios de televisión, incluye televisión por cable	servicios de television, incluye television por cable	2026-01-09 12:52:15.476768-06	1
60900	Programación y transmisión de radio y televisión	programacion y transmision de radio y television	2026-01-09 12:52:15.476768-06	1
61101	Servicio de telefonía	servicio de telefonia	2026-01-09 12:52:15.476768-06	1
61102	Servicio de Internet	servicio de internet	2026-01-09 12:52:15.476768-06	1
61103	Servicio de telefonía fija	servicio de telefonia fija	2026-01-09 12:52:15.476768-06	1
61109	Servicio de Internet n.c.p.	servicio de internet n.c.p.	2026-01-09 12:52:15.476768-06	1
61201	Servicios de telefonía celular	servicios de telefonia celular	2026-01-09 12:52:15.476768-06	1
61202	Servicios de Internet inalámbrico	servicios de internet inalambrico	2026-01-09 12:52:15.476768-06	1
61209	Servicios de telecomunicaciones inalámbrico n.c.p.	servicios de telecomunicaciones inalambrico n.c.p.	2026-01-09 12:52:15.476768-06	1
61301	Telecomunicaciones satelitales	telecomunicaciones satelitales	2026-01-09 12:52:15.476768-06	1
61309	Comunicación vía satélite n.c.p.	comunicacion via satelite n.c.p.	2026-01-09 12:52:15.476768-06	1
61900	Actividades de telecomunicación n.c.p.	actividades de telecomunicacion n.c.p.	2026-01-09 12:52:15.476768-06	1
62010	Programación Informática	programacion informatica	2026-01-09 12:52:15.476768-06	1
62020	Consultorías y gestión de servicios informáticos	consultorias y gestion de servicios informaticos	2026-01-09 12:52:15.476768-06	1
62090	Otras actividades de tecnología de información y servicios de computadora	otras actividades de tecnologia de informacion y servicios de computadora	2026-01-09 12:52:15.476768-06	1
63110	Procesamiento de datos y Actividades relacionadas	procesamiento de datos y actividades relacionadas	2026-01-09 12:52:15.476768-06	1
63120	Portales WEB	portales web	2026-01-09 12:52:15.476768-06	1
63910	Servicios de Agencias de Noticias	servicios de agencias de noticias	2026-01-09 12:52:15.476768-06	1
63990	Otros servicios de información n.c.p.	otros servicios de informacion n.c.p.	2026-01-09 12:52:15.476768-06	1
64110	Servicios provistos por el Banco Central de El salvador	servicios provistos por el banco central de el salvador	2026-01-09 12:52:15.476768-06	1
64190	Bancos	bancos	2026-01-09 12:52:15.476768-06	1
64192	Entidades dedicadas al envío de remesas	entidades dedicadas al envio de remesas	2026-01-09 12:52:15.476768-06	1
64199	Otras entidades financieras	otras entidades financieras	2026-01-09 12:52:15.476768-06	1
64200	Actividades de sociedades de cartera	actividades de sociedades de cartera	2026-01-09 12:52:15.476768-06	1
64300	Fideicomisos, fondos y otras fuentes de financiamiento	fideicomisos, fondos y otras fuentes de financiamiento	2026-01-09 12:52:15.476768-06	1
64910	Arrendamientos financieros	arrendamientos financieros	2026-01-09 12:52:15.476768-06	1
64920	Asociaciones cooperativas de ahorro y crédito dedicadas a la intermediación financiera	asociaciones cooperativas de ahorro y credito dedicadas a la intermediacion financiera	2026-01-09 12:52:15.476768-06	1
64921	Instituciones emisoras de tarjetas de crédito y otros	instituciones emisoras de tarjetas de credito y otros	2026-01-09 12:52:15.476768-06	1
64922	Tipos de crédito ncp	tipos de credito ncp	2026-01-09 12:52:15.476768-06	1
64928	Prestamistas y casas de empeño	prestamistas y casas de empeno	2026-01-09 12:52:15.476768-06	1
64990	Actividades de servicios financieros, excepto la financiación de planes de seguros y de pensiones n.c.p.	actividades de servicios financieros, excepto la financiacion de planes de seguros y de pensiones n.c.p.	2026-01-09 12:52:15.476768-06	1
65110	Planes de seguros de vida	planes de seguros de vida	2026-01-09 12:52:15.476768-06	1
65120	Planes de seguro excepto de vida	planes de seguro excepto de vida	2026-01-09 12:52:15.476768-06	1
65199	Seguros generales de todo tipo	seguros generales de todo tipo	2026-01-09 12:52:15.476768-06	1
65200	Planes se seguro	planes se seguro	2026-01-09 12:52:15.476768-06	1
65300	Planes de pensiones	planes de pensiones	2026-01-09 12:52:15.476768-06	1
66110	Administración de mercados financieros (Bolsa de Valores)	administracion de mercados financieros (bolsa de valores)	2026-01-09 12:52:15.476768-06	1
66120	Actividades bursátiles (Corredores de Bolsa)	actividades bursatiles (corredores de bolsa)	2026-01-09 12:52:15.476768-06	1
66190	Actividades auxiliares de la intermediación financiera ncp	actividades auxiliares de la intermediacion financiera ncp	2026-01-09 12:52:15.476768-06	1
66210	Evaluación de riesgos y daños	evaluacion de riesgos y danos	2026-01-09 12:52:15.476768-06	1
66220	Actividades de agentes y corredores de seguros	actividades de agentes y corredores de seguros	2026-01-09 12:52:15.476768-06	1
66290	Otras actividades auxiliares de seguros y fondos de pensiones	otras actividades auxiliares de seguros y fondos de pensiones	2026-01-09 12:52:15.476768-06	1
66300	Actividades de administración de fondos	actividades de administracion de fondos	2026-01-09 12:52:15.476768-06	1
68101	Servicio de alquiler y venta de lotes en cementerios	servicio de alquiler y venta de lotes en cementerios	2026-01-09 12:52:15.476768-06	1
68109	Actividades inmobiliarias realizadas con bienes propios o arrendados n.c.p.	actividades inmobiliarias realizadas con bienes propios o arrendados n.c.p.	2026-01-09 12:52:15.476768-06	1
68200	Actividades Inmobiliarias Realizadas a Cambio de una Retribución o por Contrata	actividades inmobiliarias realizadas a cambio de una retribucion o por contrata	2026-01-09 12:52:15.476768-06	1
69100	Actividades jurídicas	actividades juridicas	2026-01-09 12:52:15.476768-06	1
69200	Actividades de contabilidad, teneduría de libros y auditoría; asesoramiento en materia de impuestos	actividades de contabilidad, teneduria de libros y auditoria; asesoramiento en materia de impuestos	2026-01-09 12:52:15.476768-06	1
70100	Actividades de oficinas centrales de sociedades de cartera	actividades de oficinas centrales de sociedades de cartera	2026-01-09 12:52:15.476768-06	1
70200	Actividades de consultoría en gestión empresarial	actividades de consultoria en gestion empresarial	2026-01-09 12:52:15.476768-06	1
71101	Servicios de arquitectura y planificación urbana y servicios conexos	servicios de arquitectura y planificacion urbana y servicios conexos	2026-01-09 12:52:15.476768-06	1
71102	Servicios de ingeniería	servicios de ingenieria	2026-01-09 12:52:15.476768-06	1
71103	Servicios de agrimensura, topografía, cartografía, prospección y geofísica y servicios conexos	servicios de agrimensura, topografia, cartografia, prospeccion y geofisica y servicios conexos	2026-01-09 12:52:15.476768-06	1
71200	Ensayos y análisis técnicos	ensayos y analisis tecnicos	2026-01-09 12:52:15.476768-06	1
72100	Investigaciones y desarrollo experimental en el campo de las ciencias naturales y la ingeniería	investigaciones y desarrollo experimental en el campo de las ciencias naturales y la ingenieria	2026-01-09 12:52:15.476768-06	1
72199	Investigaciones científicas	investigaciones cientificas	2026-01-09 12:52:15.476768-06	1
72200	Investigaciones y desarrollo experimental en el campo de las ciencias sociales y las humanidades científica y desarrollo	investigaciones y desarrollo experimental en el campo de las ciencias sociales y las humanidades cientifica y desarrollo	2026-01-09 12:52:15.476768-06	1
73100	Publicidad	publicidad	2026-01-09 12:52:15.476768-06	1
73200	Investigación de mercados y realización de encuestas de opinión pública	investigacion de mercados y realizacion de encuestas de opinion publica	2026-01-09 12:52:15.476768-06	1
74100	Actividades de diseño especializado	actividades de diseno especializado	2026-01-09 12:52:15.476768-06	1
74200	Actividades de fotografía	actividades de fotografia	2026-01-09 12:52:15.476768-06	1
74900	Servicios profesionales y científicos ncp	servicios profesionales y cientificos ncp	2026-01-09 12:52:15.476768-06	1
75000	Actividades veterinarias	actividades veterinarias	2026-01-09 12:52:15.476768-06	1
77101	Alquiler de equipo de transporte terrestre	alquiler de equipo de transporte terrestre	2026-01-09 12:52:15.476768-06	1
77102	Alquiler de equipo de transporte acuático	alquiler de equipo de transporte acuatico	2026-01-09 12:52:15.476768-06	1
77103	Alquiler de equipo de transporte por vía aérea	alquiler de equipo de transporte por via aerea	2026-01-09 12:52:15.476768-06	1
77210	Alquiler y arrendamiento de equipo de recreo y deportivo	alquiler y arrendamiento de equipo de recreo y deportivo	2026-01-09 12:52:15.476768-06	1
77220	Alquiler de cintas de video y discos	alquiler de cintas de video y discos	2026-01-09 12:52:15.476768-06	1
77290	Alquiler de otros efectos personales y enseres domésticos	alquiler de otros efectos personales y enseres domesticos	2026-01-09 12:52:15.476768-06	1
77300	Alquiler de maquinaria y equipo	alquiler de maquinaria y equipo	2026-01-09 12:52:15.476768-06	1
77400	Arrendamiento de productos de propiedad intelectual	arrendamiento de productos de propiedad intelectual	2026-01-09 12:52:15.476768-06	1
78100	Obtención y dotación de personal	obtencion y dotacion de personal	2026-01-09 12:52:15.476768-06	1
78200	Actividades de las agencias de trabajo temporal	actividades de las agencias de trabajo temporal	2026-01-09 12:52:15.476768-06	1
78300	Dotación de recursos humanos y gestión; gestión de las funciones de recursos humanos	dotacion de recursos humanos y gestion; gestion de las funciones de recursos humanos	2026-01-09 12:52:15.476768-06	1
79110	Actividades de agencias de viajes y organizadores de viajes; actividades de asistencia a turistas	actividades de agencias de viajes y organizadores de viajes; actividades de asistencia a turistas	2026-01-09 12:52:15.476768-06	1
79120	Actividades de los operadores turísticos	actividades de los operadores turisticos	2026-01-09 12:52:15.476768-06	1
79900	Otros servicios de reservas y actividades relacionadas	otros servicios de reservas y actividades relacionadas	2026-01-09 12:52:15.476768-06	1
80100	Servicios de seguridad privados	servicios de seguridad privados	2026-01-09 12:52:15.476768-06	1
80201	Actividades de servicios de sistemas de seguridad	actividades de servicios de sistemas de seguridad	2026-01-09 12:52:15.476768-06	1
80202	Actividades para la prestación de sistemas de seguridad	actividades para la prestacion de sistemas de seguridad	2026-01-09 12:52:15.476768-06	1
80300	Actividades de investigación	actividades de investigacion	2026-01-09 12:52:15.476768-06	1
81100	Actividades combinadas de mantenimiento de edificios e instalaciones	actividades combinadas de mantenimiento de edificios e instalaciones	2026-01-09 12:52:15.476768-06	1
81210	Limpieza general de edificios	limpieza general de edificios	2026-01-09 12:52:15.476768-06	1
81290	Otras actividades combinadas de mantenimiento de edificios e instalaciones ncp	otras actividades combinadas de mantenimiento de edificios e instalaciones ncp	2026-01-09 12:52:15.476768-06	1
82110	Servicios administrativos de oficinas	servicios administrativos de oficinas	2026-01-09 12:52:15.476768-06	1
82190	Servicio de fotocopiado y similares, excepto en imprentas	servicio de fotocopiado y similares, excepto en imprentas	2026-01-09 12:52:15.476768-06	1
82200	Actividades de las centrales de llamadas (call center)	actividades de las centrales de llamadas (call center)	2026-01-09 12:52:15.476768-06	1
82300	Organización de convenciones y ferias de negocios	organizacion de convenciones y ferias de negocios	2026-01-09 12:52:15.476768-06	1
82910	Actividades de agencias de cobro y oficinas de crédito	actividades de agencias de cobro y oficinas de credito	2026-01-09 12:52:15.476768-06	1
82921	Servicios de envase y empaque de productos alimenticios	servicios de envase y empaque de productos alimenticios	2026-01-09 12:52:15.476768-06	1
82922	Servicios de envase y empaque de productos medicinales	servicios de envase y empaque de productos medicinales	2026-01-09 12:52:15.476768-06	1
82929	Servicio de envase y empaque ncp	servicio de envase y empaque ncp	2026-01-09 12:52:15.476768-06	1
82990	Actividades de apoyo empresariales ncp	actividades de apoyo empresariales ncp	2026-01-09 12:52:15.476768-06	1
84110	Actividades de la Administración Pública en general	actividades de la administracion publica en general	2026-01-09 12:52:15.476768-06	1
84111	Alcaldías Municipales	alcaldias municipales	2026-01-09 12:52:15.476768-06	1
84120	Regulación de las actividades de prestación de servicios sanitarios, educativos, culturales y otros servicios sociales, excepto seguridad social	regulacion de las actividades de prestacion de servicios sanitarios, educativos, culturales y otros servicios sociales, excepto seguridad social	2026-01-09 12:52:15.476768-06	1
84130	Regulación y facilitación de la actividad económica	regulacion y facilitacion de la actividad economica	2026-01-09 12:52:15.476768-06	1
84210	Actividades de administración y funcionamiento del Ministerio de Relaciones Exteriores	actividades de administracion y funcionamiento del ministerio de relaciones exteriores	2026-01-09 12:52:15.476768-06	1
84220	Actividades de defensa	actividades de defensa	2026-01-09 12:52:15.476768-06	1
84230	Actividades de mantenimiento del orden público y de seguridad	actividades de mantenimiento del orden publico y de seguridad	2026-01-09 12:52:15.476768-06	1
84300	Actividades de planes de seguridad social de afiliación obligatoria	actividades de planes de seguridad social de afiliacion obligatoria	2026-01-09 12:52:15.476768-06	1
85101	Guardería educativa	guarderia educativa	2026-01-09 12:52:15.476768-06	1
85102	Enseñanza preescolar o parvularia	ensenanza preescolar o parvularia	2026-01-09 12:52:15.476768-06	1
85103	Enseñanza primaria	ensenanza primaria	2026-01-09 12:52:15.476768-06	1
85104	Servicio de educación preescolar y primaria integrada	servicio de educacion preescolar y primaria integrada	2026-01-09 12:52:15.476768-06	1
85211	Enseñanza secundaria tercer ciclo (7°, 8° y 9°)	ensenanza secundaria tercer ciclo (7°, 8° y 9°)	2026-01-09 12:52:15.476768-06	1
85212	Enseñanza secundaria de formación general bachillerato	ensenanza secundaria de formacion general bachillerato	2026-01-09 12:52:15.476768-06	1
85221	Enseñanza secundaria de formación técnica y profesional	ensenanza secundaria de formacion tecnica y profesional	2026-01-09 12:52:15.476768-06	1
85222	Enseñanza secundaria de formación técnica y profesional integrada con enseñanza primaria	ensenanza secundaria de formacion tecnica y profesional integrada con ensenanza primaria	2026-01-09 12:52:15.476768-06	1
85301	Enseñanza superior universitaria	ensenanza superior universitaria	2026-01-09 12:52:15.476768-06	1
85302	Enseñanza superior no universitaria	ensenanza superior no universitaria	2026-01-09 12:52:15.476768-06	1
85303	Enseñanza superior integrada a educación secundaria y/o primaria	ensenanza superior integrada a educacion secundaria y/o primaria	2026-01-09 12:52:15.476768-06	1
85410	Educación deportiva y recreativa	educacion deportiva y recreativa	2026-01-09 12:52:15.476768-06	1
85420	Educación cultural	educacion cultural	2026-01-09 12:52:15.476768-06	1
85490	Otros tipos de enseñanza n.c.p.	otros tipos de ensenanza n.c.p.	2026-01-09 12:52:15.476768-06	1
85499	Enseñanza formal	ensenanza formal	2026-01-09 12:52:15.476768-06	1
85500	Servicios de apoyo a la enseñanza	servicios de apoyo a la ensenanza	2026-01-09 12:52:15.476768-06	1
86100	Actividades de hospitales	actividades de hospitales	2026-01-09 12:52:15.476768-06	1
86201	Clínicas médicas	clinicas medicas	2026-01-09 12:52:15.476768-06	1
86202	Servicios de Odontología	servicios de odontologia	2026-01-09 12:52:15.476768-06	1
86203	Servicios médicos	servicios medicos	2026-01-09 12:52:15.476768-06	1
86901	Servicios de análisis y estudios de diagnóstico	servicios de analisis y estudios de diagnostico	2026-01-09 12:52:15.476768-06	1
86902	Actividades de atención de la salud humana	actividades de atencion de la salud humana	2026-01-09 12:52:15.476768-06	1
86909	Otros Servicio relacionados con la salud ncp	otros servicio relacionados con la salud ncp	2026-01-09 12:52:15.476768-06	1
87100	Residencias de ancianos con atención de enfermería	residencias de ancianos con atencion de enfermeria	2026-01-09 12:52:15.476768-06	1
87200	Instituciones dedicadas al tratamiento del retraso mental, problemas de salud mental y el uso indebido de sustancias nocivas	instituciones dedicadas al tratamiento del retraso mental, problemas de salud mental y el uso indebido de sustancias nocivas	2026-01-09 12:52:15.476768-06	1
87300	Instituciones dedicadas al cuidado de ancianos y discapacitados	instituciones dedicadas al cuidado de ancianos y discapacitados	2026-01-09 12:52:15.476768-06	1
87900	Actividades de asistencia a niños y jóvenes	actividades de asistencia a ninos y jovenes	2026-01-09 12:52:15.476768-06	1
87901	Otras actividades de atención en instituciones	otras actividades de atencion en instituciones	2026-01-09 12:52:15.476768-06	1
88100	Actividades de asistencia sociales sin alojamiento para ancianos y discapacitados	actividades de asistencia sociales sin alojamiento para ancianos y discapacitados	2026-01-09 12:52:15.476768-06	1
88900	servicios sociales sin alojamiento ncp	servicios sociales sin alojamiento ncp	2026-01-09 12:52:15.476768-06	1
90000	Actividades creativas artísticas y de esparcimiento	actividades creativas artisticas y de esparcimiento	2026-01-09 12:52:15.476768-06	1
91010	Actividades de bibliotecas y archivos	actividades de bibliotecas y archivos	2026-01-09 12:52:15.476768-06	1
91020	Actividades de museos y preservación de lugares y edificios históricos	actividades de museos y preservacion de lugares y edificios historicos	2026-01-09 12:52:15.476768-06	1
91030	Actividades de jardines botánicos, zoológicos y de reservas naturales	actividades de jardines botanicos, zoologicos y de reservas naturales	2026-01-09 12:52:15.476768-06	1
92000	Actividades de juegos y apuestas	actividades de juegos y apuestas	2026-01-09 12:52:15.476768-06	1
93110	Gestión de instalaciones deportivas	gestion de instalaciones deportivas	2026-01-09 12:52:15.476768-06	1
93120	Actividades de clubes deportivos	actividades de clubes deportivos	2026-01-09 12:52:15.476768-06	1
93190	Otras actividades deportivas	otras actividades deportivas	2026-01-09 12:52:15.476768-06	1
93210	Actividades de parques de atracciones y parques temáticos	actividades de parques de atracciones y parques tematicos	2026-01-09 12:52:15.476768-06	1
93291	Discotecas y salas de baile	discotecas y salas de baile	2026-01-09 12:52:15.476768-06	1
93298	Centros vacacionales	centros vacacionales	2026-01-09 12:52:15.476768-06	1
93299	Actividades de esparcimiento ncp	actividades de esparcimiento ncp	2026-01-09 12:52:15.476768-06	1
94110	Actividades de organizaciones empresariales y de empleadores	actividades de organizaciones empresariales y de empleadores	2026-01-09 12:52:15.476768-06	1
94120	Actividades de organizaciones profesionales	actividades de organizaciones profesionales	2026-01-09 12:52:15.476768-06	1
94200	Actividades de sindicatos	actividades de sindicatos	2026-01-09 12:52:15.476768-06	1
94910	Actividades de organizaciones religiosas	actividades de organizaciones religiosas	2026-01-09 12:52:15.476768-06	1
94920	Actividades de organizaciones políticas	actividades de organizaciones politicas	2026-01-09 12:52:15.476768-06	1
94990	Actividades de asociaciones n.c.p.	actividades de asociaciones n.c.p.	2026-01-09 12:52:15.476768-06	1
95110	Reparación de computadoras y equipo periférico	reparacion de computadoras y equipo periferico	2026-01-09 12:52:15.476768-06	1
95120	Reparación de equipo de comunicación	reparacion de equipo de comunicacion	2026-01-09 12:52:15.476768-06	1
95210	Reparación de aparatos electrónicos de consumo	reparacion de aparatos electronicos de consumo	2026-01-09 12:52:15.476768-06	1
95220	Reparación de aparatos doméstico y equipo de hogar y jardín	reparacion de aparatos domestico y equipo de hogar y jardin	2026-01-09 12:52:15.476768-06	1
95230	Reparación de calzado y artículos de cuero	reparacion de calzado y articulos de cuero	2026-01-09 12:52:15.476768-06	1
95240	Reparación de muebles y accesorios para el hogar	reparacion de muebles y accesorios para el hogar	2026-01-09 12:52:15.476768-06	1
95291	Reparación de Instrumentos musicales	reparacion de instrumentos musicales	2026-01-09 12:52:15.476768-06	1
95292	Servicios de cerrajería y copiado de llaves	servicios de cerrajeria y copiado de llaves	2026-01-09 12:52:15.476768-06	1
95293	Reparación de joyas y relojes	reparacion de joyas y relojes	2026-01-09 12:52:15.476768-06	1
95294	Reparación de bicicletas, sillas de ruedas y rodados n.c.p.	reparacion de bicicletas, sillas de ruedas y rodados n.c.p.	2026-01-09 12:52:15.476768-06	1
95299	Reparaciones de enseres personales n.c.p.	reparaciones de enseres personales n.c.p.	2026-01-09 12:52:15.476768-06	1
96010	Lavado y limpieza de prendas de tela y de piel, incluso la limpieza en seco	lavado y limpieza de prendas de tela y de piel, incluso la limpieza en seco	2026-01-09 12:52:15.476768-06	1
96020	Peluquería y otros tratamientos de belleza	peluqueria y otros tratamientos de belleza	2026-01-09 12:52:15.476768-06	1
96030	Pompas fúnebres y actividades conexas	pompas funebres y actividades conexas	2026-01-09 12:52:15.476768-06	1
96091	Servicios de sauna y otros servicios para la estética corporal n.c.p.	servicios de sauna y otros servicios para la estetica corporal n.c.p.	2026-01-09 12:52:15.476768-06	1
96092	Servicios n.c.p.	servicios n.c.p.	2026-01-09 12:52:15.476768-06	1
97000	Actividad de los hogares en calidad de empleadores de personal doméstico	actividad de los hogares en calidad de empleadores de personal domestico	2026-01-09 12:52:15.476768-06	1
98100	Actividades indiferenciadas de producción de bienes de los hogares privados para uso propio	actividades indiferenciadas de produccion de bienes de los hogares privados para uso propio	2026-01-09 12:52:15.476768-06	1
98200	Actividades indiferenciadas de producción de servicios de los hogares privados para uso propio	actividades indiferenciadas de produccion de servicios de los hogares privados para uso propio	2026-01-09 12:52:15.476768-06	1
99000	Actividades de organizaciones y órganos extraterritoriales	actividades de organizaciones y organos extraterritoriales	2026-01-09 12:52:15.476768-06	1
10001	Empleados	empleados	2026-01-09 12:52:15.476768-06	1
10002	Pensionado	pensionado	2026-01-09 12:52:15.476768-06	1
10003	Estudiante	estudiante	2026-01-09 12:52:15.476768-06	1
10004	Desempleado	desempleado	2026-01-09 12:52:15.476768-06	1
10005	Otros	otros	2026-01-09 12:52:15.476768-06	1
10006	Comerciante	comerciante	2026-01-09 12:52:15.476768-06	1
\.


--
-- Data for Name: geo_departments; Type: TABLE DATA; Schema: public; Owner: jarvis
--

COPY public.geo_departments (code, name, normalized, updated_at, version) FROM stdin;
00	OTRO (PARA EXTRANJEROS)	otro (para extranjeros)	2025-11-11 04:37:12.280441-06	1
01	AHUACHAPÁN	ahuachapan	2025-11-11 04:37:12.280441-06	1
02	SANTA ANA	santa ana	2025-11-11 04:37:12.280441-06	1
03	SONSONATE	sonsonate	2025-11-11 04:37:12.280441-06	1
04	CHALATENANGO	chalatenango	2025-11-11 04:37:12.280441-06	1
05	LA LIBERTAD	la libertad	2025-11-11 04:37:12.280441-06	1
06	SAN SALVADOR	san salvador	2025-11-11 04:37:12.280441-06	1
07	CUSCATLÁN	cuscatlan	2025-11-11 04:37:12.280441-06	1
08	LA PAZ	la paz	2025-11-11 04:37:12.280441-06	1
09	CABAÑAS	cabanas	2025-11-11 04:37:12.280441-06	1
10	SAN VICENTE	san vicente	2025-11-11 04:37:12.280441-06	1
11	USULUTÁN	usulutan	2025-11-11 04:37:12.280441-06	1
12	SAN MIGUEL	san miguel	2025-11-11 04:37:12.280441-06	1
13	MORAZÁN	morazan	2025-11-11 04:37:12.280441-06	1
14	LA UNIÓN	la union	2025-11-11 04:37:12.280441-06	1
\.


--
-- Data for Name: geo_municipalities; Type: TABLE DATA; Schema: public; Owner: jarvis
--

COPY public.geo_municipalities (id, dept_code, muni_code, name, normalized, updated_at, version) FROM stdin;
34	00	00	OTRO (PARA EXTRANJEROS)	otro (para extranjeros)	2025-11-11 04:37:12.280441-06	1
35	01	13	AHUACHAPAN NORTE	ahuachapan norte	2025-11-11 04:37:12.280441-06	1
36	01	14	AHUACHAPAN CENTRO	ahuachapan centro	2025-11-11 04:37:12.280441-06	1
37	01	15	AHUACHAPAN SUR	ahuachapan sur	2025-11-11 04:37:12.280441-06	1
38	02	14	SANTA ANA NORTE	santa ana norte	2025-11-11 04:37:12.280441-06	1
39	02	15	SANTA ANA CENTRO	santa ana centro	2025-11-11 04:37:12.280441-06	1
40	02	16	SANTA ANA ESTE	santa ana este	2025-11-11 04:37:12.280441-06	1
41	02	17	SANTA ANA OESTE	santa ana oeste	2025-11-11 04:37:12.280441-06	1
42	03	17	SONSONATE NORTE	sonsonate norte	2025-11-11 04:37:12.280441-06	1
43	03	18	SONSONATE CENTRO	sonsonate centro	2025-11-11 04:37:12.280441-06	1
44	03	19	SONSONATE ESTE	sonsonate este	2025-11-11 04:37:12.280441-06	1
45	03	20	SONSONATE OESTE	sonsonate oeste	2025-11-11 04:37:12.280441-06	1
46	04	34	CHALATENANGO NORTE	chalatenango norte	2025-11-11 04:37:12.280441-06	1
47	04	35	CHALATENANGO CENTRO	chalatenango centro	2025-11-11 04:37:12.280441-06	1
48	04	36	CHALATENANGO SUR	chalatenango sur	2025-11-11 04:37:12.280441-06	1
49	05	23	LA LIBERTAD NORTE	la libertad norte	2025-11-11 04:37:12.280441-06	1
50	05	24	LA LIBERTAD CENTRO	la libertad centro	2025-11-11 04:37:12.280441-06	1
51	05	25	LA LIBERTAD OESTE	la libertad oeste	2025-11-11 04:37:12.280441-06	1
52	05	26	LA LIBERTAD ESTE	la libertad este	2025-11-11 04:37:12.280441-06	1
53	05	27	LA LIBERTAD COSTA	la libertad costa	2025-11-11 04:37:12.280441-06	1
54	05	28	LA LIBERTAD SUR	la libertad sur	2025-11-11 04:37:12.280441-06	1
55	06	20	SAN SALVADOR NORTE	san salvador norte	2025-11-11 04:37:12.280441-06	1
56	06	21	SAN SALVADOR OESTE	san salvador oeste	2025-11-11 04:37:12.280441-06	1
57	06	22	SAN SALVADOR ESTE	san salvador este	2025-11-11 04:37:12.280441-06	1
58	06	23	SAN SALVADOR CENTRO	san salvador centro	2025-11-11 04:37:12.280441-06	1
59	06	24	SAN SALVADOR SUR	san salvador sur	2025-11-11 04:37:12.280441-06	1
60	07	17	CUSCATLAN NORTE	cuscatlan norte	2025-11-11 04:37:12.280441-06	1
61	07	18	CUSCATLAN SUR	cuscatlan sur	2025-11-11 04:37:12.280441-06	1
62	08	23	LA PAZ OESTE	la paz oeste	2025-11-11 04:37:12.280441-06	1
63	08	24	LA PAZ CENTRO	la paz centro	2025-11-11 04:37:12.280441-06	1
64	08	25	LA PAZ ESTE	la paz este	2025-11-11 04:37:12.280441-06	1
65	09	10	CABAÑAS OESTE	cabanas oeste	2025-11-11 04:37:12.280441-06	1
66	09	11	CABAÑAS ESTE	cabanas este	2025-11-11 04:37:12.280441-06	1
67	10	14	SAN VICENTE NORTE	san vicente norte	2025-11-11 04:37:12.280441-06	1
68	10	15	SAN VICENTE SUR	san vicente sur	2025-11-11 04:37:12.280441-06	1
69	11	24	USULUTAN NORTE	usulutan norte	2025-11-11 04:37:12.280441-06	1
70	11	25	USULUTAN ESTE	usulutan este	2025-11-11 04:37:12.280441-06	1
71	11	26	USULUTAN OESTE	usulutan oeste	2025-11-11 04:37:12.280441-06	1
72	12	21	SAN MIGUEL NORTE	san miguel norte	2025-11-11 04:37:12.280441-06	1
73	12	22	SAN MIGUEL CENTRO	san miguel centro	2025-11-11 04:37:12.280441-06	1
74	12	23	SAN MIGUEL OESTE	san miguel oeste	2025-11-11 04:37:12.280441-06	1
75	13	27	MORAZAN NORTE	morazan norte	2025-11-11 04:37:12.280441-06	1
76	13	28	MORAZAN SUR	morazan sur	2025-11-11 04:37:12.280441-06	1
77	14	19	LA UNION NORTE	la union norte	2025-11-11 04:37:12.280441-06	1
78	14	20	LA UNION SUR	la union sur	2025-11-11 04:37:12.280441-06	1
\.


--
-- Name: geo_municipalities_id_seq; Type: SEQUENCE SET; Schema: public; Owner: jarvis
--

SELECT pg_catalog.setval('public.geo_municipalities_id_seq', 78, true);


--
-- Name: activities_catalog activities_catalog_pkey; Type: CONSTRAINT; Schema: public; Owner: jarvis
--

ALTER TABLE ONLY public.activities_catalog
    ADD CONSTRAINT activities_catalog_pkey PRIMARY KEY (code);


--
-- Name: geo_departments geo_departments_pkey; Type: CONSTRAINT; Schema: public; Owner: jarvis
--

ALTER TABLE ONLY public.geo_departments
    ADD CONSTRAINT geo_departments_pkey PRIMARY KEY (code);


--
-- Name: geo_municipalities geo_municipalities_dept_code_muni_code_key; Type: CONSTRAINT; Schema: public; Owner: jarvis
--

ALTER TABLE ONLY public.geo_municipalities
    ADD CONSTRAINT geo_municipalities_dept_code_muni_code_key UNIQUE (dept_code, muni_code);


--
-- Name: geo_municipalities geo_municipalities_dept_code_normalized_key; Type: CONSTRAINT; Schema: public; Owner: jarvis
--

ALTER TABLE ONLY public.geo_municipalities
    ADD CONSTRAINT geo_municipalities_dept_code_normalized_key UNIQUE (dept_code, normalized);


--
-- Name: geo_municipalities geo_municipalities_pkey; Type: CONSTRAINT; Schema: public; Owner: jarvis
--

ALTER TABLE ONLY public.geo_municipalities
    ADD CONSTRAINT geo_municipalities_pkey PRIMARY KEY (id);


--
-- Name: ix_activities_catalog_updated_at; Type: INDEX; Schema: public; Owner: jarvis
--

CREATE INDEX ix_activities_catalog_updated_at ON public.activities_catalog USING btree (updated_at);


--
-- Name: ix_activities_norm; Type: INDEX; Schema: public; Owner: jarvis
--

CREATE INDEX ix_activities_norm ON public.activities_catalog USING btree (normalized);


--
-- Name: ix_geo_departments_updated_at; Type: INDEX; Schema: public; Owner: jarvis
--

CREATE INDEX ix_geo_departments_updated_at ON public.geo_departments USING btree (updated_at);


--
-- Name: ix_geo_dept_norm; Type: INDEX; Schema: public; Owner: jarvis
--

CREATE INDEX ix_geo_dept_norm ON public.geo_departments USING btree (normalized);


--
-- Name: ix_geo_municipalities_updated_at; Type: INDEX; Schema: public; Owner: jarvis
--

CREATE INDEX ix_geo_municipalities_updated_at ON public.geo_municipalities USING btree (updated_at);


--
-- Name: geo_municipalities fk_geo_muni_dept; Type: FK CONSTRAINT; Schema: public; Owner: jarvis
--

ALTER TABLE ONLY public.geo_municipalities
    ADD CONSTRAINT fk_geo_muni_dept FOREIGN KEY (dept_code) REFERENCES public.geo_departments(code);


--
-- PostgreSQL database dump complete
--

\unrestrict nkm2P1o9nXlRxGtCDuxMDPiHQF6CPeISHQDpWdyUCuYPCDfyxKARTj6aXZ8aFm4

