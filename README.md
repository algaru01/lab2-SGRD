# lab2-SGRD

## Autor
Alejandro Gálvez Ruiz

## Enunciado
Obtener una clave de encriptado de un **archivo _gpg_** sabiendo únicamente que esta contenía solamente **carácteres en minúscula**.

Para ello se diseñará un programa que haga _brute force_ al archivo objetivo.

## Dependencias
Para la instalación de los paquetes necesarios puede hacer uso de:
```shell
pip install -r requirements.txt
```

## Ejecución
Para ejecutar el _script_ use:
```shell
python3 brute_force.py --file [archivo GPG]
```
También existe la posibilidad de indicar el número de _cores_ que quiere usar con la opción:
```shell
python3 brute_force.py --file [archivo GPG] --cores [n_cores]
```
O indicar si prefiere hacer uso o no del _multithreading_:
```shell
python3 brute_force.py --file [archivo GPG] --no-multithreading
```
Para más información use el comando _help_:
```shell
python3 brute_force.py --help
```

## Resultado
El resultado del _script_ será mostrado en pantalla, seguido de una estimación del tiempo necesario para la búsqueda.
También se escribirá la clave en un archivo de texto en:
```
keys_found/[nombre_archivo_gpg]_key.txt
```
