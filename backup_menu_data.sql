--
-- PostgreSQL database dump
--

\restrict EJzyBUuJcHVSq0Hd5zNfqMvBPdawU74IzMO5VcIZG0Oc9hnBIYCohHXjMWLQpfH

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

--
-- Data for Name: menu_category; Type: TABLE DATA; Schema: public; Owner: jarvis
--

COPY public.menu_category (id, name, is_active, is_hidden, "position") FROM stdin;
4	BURRITOS	t	f	0
14	SIN CATEGORÍA (ARCHIVADOS)	t	t	6
5	BOWLS	t	f	4
15	DRINKS	t	f	1
8	NACHOS	t	f	2
7	QUESADILLAS	t	f	3
10	SIDES	t	f	5
9	SNACKS	t	f	6
6	TACOS	t	f	7
\.


--
-- Data for Name: menu_product; Type: TABLE DATA; Schema: public; Owner: jarvis
--

COPY public.menu_product (id, name, description, price, image, available, category_id, image_path, requires_kitchen, is_archived, modifier_group_order, disposable_apply_to, disposable_fee, sort_order) FROM stdin;
3	PAPAS FRITAS	Papas fritas	4.00	ALMUERZO/9989ea4655394eaf905234aa745bc34b.jpg	f	14	/media/ALMUERZO/9989ea4655394eaf905234aa745bc34b.jpg	f	t	[2, 8, 7]	[]	0.00	0
2	PLATO DE CARNE	Carne asada con verduras y arroz	3.00	ALMUERZO/afa015b9337d4206895d456c60c45be6.jpeg	f	14	/menu_image/ALMUERZO/afa015b9337d4206895d456c60c45be6.jpeg	f	t	[]	[]	0.00	1
1	PLATO DE PECHUGA	Plato de Pollo con arroz blanco y salsa de hongos	2.50	ALMUERZO/f22776223ba44ed7bb945497de70c84f.jpg	f	14	/menu_image/ALMUERZO/f22776223ba44ed7bb945497de70c84f.jpg	f	t	[]	[]	0.00	2
7	Beef Barbacoa Burrito	Construye tu propio burrito	8.99	menu_image/BURRITOS/6d5d5e6f265b434abd5bfcc1e084db3b.png	f	4	/media/menu_image/BURRITOS/6d5d5e6f265b434abd5bfcc1e084db3b.png	t	t	[6, 3, 5, 1, 4]	["takeout"]	1.50	0
5	Carne Asada Burrito	Construye tu propio burrito	8.99	menu_image/BURRITOS/f16a23b77edb47348a69bc2b6ded1714.png	f	4	/media/menu_image/BURRITOS/f16a23b77edb47348a69bc2b6ded1714.png	f	t	[]	[]	0.00	1
6	Char-Grilled Pastor Burrito	Construye tu propio burrito	7.99	menu_image/BURRITOS/eb650b9aee4a49cbb5e541d6c7943622.png	f	4	/media/menu_image/BURRITOS/eb650b9aee4a49cbb5e541d6c7943622.png	f	t	[]	[]	0.00	2
4	Grilled Chicken Burrito	Construye tu propio burrito	7.99	menu_image/BURRITOS/d3c203e6581b4df3a5f5c6e10cef4b14.png	f	4	/media/menu_image/BURRITOS/d3c203e6581b4df3a5f5c6e10cef4b14.png	f	t	[]	[]	0.00	3
9	Carne Asada Bowl	Build your own burrito.	8.99	menu_image/BURRITOS/0d9a08c0b0724af8bc178aa746470b8b.png	t	5	/media/menu_image/BURRITOS/0d9a08c0b0724af8bc178aa746470b8b.png	f	f	[12, 3, 19, 4, 5, 6, 20, 13]	["takeout", "delivery"]	0.27	5
\.


--
-- Name: menu_category_id_seq; Type: SEQUENCE SET; Schema: public; Owner: jarvis
--

SELECT pg_catalog.setval('public.menu_category_id_seq', 15, true);


--
-- Name: menu_product_id_seq; Type: SEQUENCE SET; Schema: public; Owner: jarvis
--

SELECT pg_catalog.setval('public.menu_product_id_seq', 9, true);


--
-- PostgreSQL database dump complete
--

\unrestrict EJzyBUuJcHVSq0Hd5zNfqMvBPdawU74IzMO5VcIZG0Oc9hnBIYCohHXjMWLQpfH

