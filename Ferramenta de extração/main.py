from ConexãoBanco import nos, start_time
from Neo4j import marcar_propriedades_compartilhadas, definir_enum
import time

print("-----------------------")
# Chamar a função para marcar propriedades compartilhadas
marcar_propriedades_compartilhadas(nos)
print("-----------------------")

def gerar_saida_pg_schema(nos):
    schema = "CREATE GRAPH TYPE TesteGraphType STRICT {\n"

    # percorre sobre os nós e suas propriedades
    for rotulos, no in nos.items():
        rotulos_str = ' & '.join(rotulos)
        schema += f"({rotulos_str}Type : {rotulos_str} {{\n"

        # Sobre as propriedades do nó
        for propriedade, info_propriedade in no.propriedades.items():
            tipo_propriedade = max(info_propriedade["tipos"], key=info_propriedade["tipos"].get)  # tipo da propriedade com a maior ocorrência

            # Verificar se a propriedade é uma enumeração
            quantidadeNosTotal = no.quantidade
            definir_enum(quantidadeNosTotal, info_propriedade, no)

            # Verificar se a propriedade é opcional
            opcional = False
            if no.quantidade != info_propriedade["total"]:
                opcional = True

            compartilhada = False
            if info_propriedade["is_shared"]:
                compartilhada = True

            # Verificar se a propriedade tem constraint MANDATORY
            if "MANDATORY" in info_propriedade["constraintList"]:
                schema += f"    MANDATORY {propriedade} {tipo_propriedade.upper()},\n"
            # Verificar se a propriedade tem constraint SINGLETON
            # if "SINGLETON" in info_propriedade["constraintList"]:
            #     schema += f"    SINGLETON {propriedade} {tipo_propriedade.upper()},\n"

            if info_propriedade.get("is_enum"):
                valores_enum = ', '.join(f'"{val}"' for val in info_propriedade.get("values"))

                if opcional:
                    if compartilhada:
                        schema += f"    OPTIONAL *{propriedade} ENUM ({valores_enum}),\n"
                    else:
                        schema += f"    OPTIONAL {propriedade} ENUM ({valores_enum}),\n"
                else:
                    if compartilhada:
                        schema += f"    *{propriedade} ENUM ({valores_enum}),\n"
                    else:
                        schema += f"    {propriedade} ENUM ({valores_enum}),\n"

            else:
                # Ajustar o tipo LIST conforme o PG-SCHEMA
                if info_propriedade["is_list"]:
                    tipo_propriedade = "array"
                    tipo_maior_freq = max(info_propriedade["tipos_listas"], key=info_propriedade["tipos_listas"].get)  # Pega o tipo mais frequente armazanado na lista
                    tam_min_lista = float('inf')
                    tam_max_lista = float('-inf')

                    for tamanho in info_propriedade["tamQuantLista"]:
                        if tamanho < tam_min_lista:
                            tam_min_lista = tamanho
                        if tamanho > tam_max_lista:
                            tam_max_lista = tamanho

                    if opcional:
                        if compartilhada:
                            schema += f"    OPTIONAL *{propriedade} {tipo_propriedade.upper()} {tipo_maior_freq} ({tam_min_lista}, {tam_max_lista}),\n"
                        else:
                            schema += f"    OPTIONAL {propriedade} {tipo_propriedade.upper()} {tipo_maior_freq} ({tam_min_lista}, {tam_max_lista}),\n"
                    else:
                        if compartilhada:
                            schema += f"    *{propriedade} {tipo_propriedade.upper()} {tipo_maior_freq} ({tam_min_lista}, {tam_max_lista}),\n"
                        else:
                            schema += f"    {propriedade} {tipo_propriedade.upper()} {tipo_maior_freq} ({tam_min_lista}, {tam_max_lista}),\n"
                else:
                    if opcional:
                        if compartilhada:
                            schema += f"    OPTIONAL *{propriedade} {tipo_propriedade.upper()},\n"
                        else:
                            schema += f"    OPTIONAL {propriedade} {tipo_propriedade.upper()},\n"
                    else:
                        if compartilhada:
                            schema += f"    *{propriedade} {tipo_propriedade.upper()},\n"
                        else:
                            schema += f"    {propriedade} {tipo_propriedade.upper()},\n"

        schema = schema.rstrip(",\n")  # Remover a última vírgula e quebra de linha
        schema += "}),\n\n"

    # Iterar sobre os relacionamentos
    relacionamentos = set()  # Conjunto para armazenar os tipos de relacionamento já adicionados
    for rotulos, no in nos.items():
        for tipo_relacionamento, relacoes in no.relacionamentos.items():
            for destino, quantidade_rel in relacoes:
                destinos_str = ' & '.join(destino)
                cardinalidade = no.cardinalidades.get(tipo_relacionamento, "")  # Verificar se há cardinalidade
                tipos_origem = ' | '.join(rotulos) if len(rotulos) > 1 else rotulos[0]

                # Verificar se o tipo de relacionamento já foi adicionado anteriormente
                if (tipos_origem, tipo_relacionamento, destinos_str) not in relacionamentos:
                    # Adicionar relacionamento apenas se não tiver sido adicionado antes
                    schema += f"(:{tipos_origem})-[{tipo_relacionamento}Type {cardinalidade}]->(:{destinos_str}Type),\n"
                    relacionamentos.add((tipos_origem, tipo_relacionamento, destinos_str))

    # Remover a última vírgula e quebra de linha
    schema = schema.rstrip(",\n")
    # Adicionar as constraints FOR do PG-SCHEMA
    schema += "\n\n"

    # Definir as constraints como Singleton ou Mandatory
    threshold_mandatory = 0.90  # Definir o threshold de 90%

    for rotulos, no in nos.items():
        for propriedade, info_propriedade in no.propriedades.items():
            quantidade_presentes = info_propriedade["total"]  # Quantidade de nodos que possuem a propriedade
            quantidade_nodos = no.quantidade  # Total de nodos desse tipo

            # Verificar se a propriedade está presente em mais de 90% dos nodos
            if quantidade_presentes / quantidade_nodos >= threshold_mandatory:
                # print(quantidade_presentes/quantidade_nodos)
                rotulos_str = ':'.join(rotulos)
                schema += f"FOR (x:{rotulos_str}Type) MANDATORY x.{propriedade},\n"

    schema += "\n"

    # listaProp = []  # Lista para armazenar todas as propriedades da lista
    
    singleton_inserido = set()

    for rotulos, no in nos.items():
        # print(rotulos)
        for propriedade, info_propriedade in no.propriedades.items():
            # print(info_propriedade["constraint"], info_propriedade["constraintList"], info_propriedade["listProp"], info_propriedade["listConstProp"])
                    
            if info_propriedade["constraint"] and "UNIQUENESS" in info_propriedade["constraintList"]:
                rotulos_str = ':'.join(rotulos)

                listaProp = []

                if len(nos[rotulos].listaChaveUnica):
                    listaProp.extend(nos[rotulos].listaChaveUnica)  # Adiciona as propriedades à lista
                    propriedades_concatenadas = ', '.join(listaProp)  # Concatena todas as propriedades em uma única string

                    chave_singleton = (rotulos_str, propriedades_concatenadas)

                    if chave_singleton not in singleton_inserido:

                        if len(listaProp) > 1 and len(listaProp) <= 2:
                            # print(propriedades_concatenadas)
                            schema += f"FOR (x:{rotulos_str}Type) SINGLETON x.({propriedades_concatenadas}),\n"
                        elif len(listaProp) == 1:
                            schema += f"FOR (x:{rotulos_str}Type) SINGLETON x.{propriedades_concatenadas},\n"
                    
                    singleton_inserido.add(chave_singleton)
                    break

                if info_propriedade["listConstProp"] and info_propriedade['unicidadeNeo4j']:
                    # print(nos[rotulos].listaChaveUnica)
                    listaProp.extend(info_propriedade["listProp"])  # Adiciona as propriedades à lista
                    propriedades_concatenadas = ', '.join(listaProp)  # Concatena todas as propriedades em uma única string

                    if len(listaProp) > 1 and len(listaProp) <= 2:
                        # print(propriedades_concatenadas)
                        schema += f"FOR (x:{rotulos_str}Type) SINGLETON x.({propriedades_concatenadas}),\n"
                    elif len(listaProp) == 1:
                        schema += f"FOR (x:{rotulos_str}Type) SINGLETON x.{propriedades_concatenadas},\n"
                else:
                    schema += f"FOR (x:{rotulos_str}Type) SINGLETON x.{propriedade},\n"

    schema = schema.rstrip(",\n")  # Remover a última vírgula e quebra de linha
    schema += "\n}"

    end_time = time.time()  # Marcar o tempo de término
    elapsed_time = end_time - start_time  # Calcular o tempo decorrido

    print(f"Tempo de execução: {elapsed_time:.2f} segundos")

    return schema

# gerar a saída PG-SCHEMA
saida_pg_schema = gerar_saida_pg_schema(nos)
print(saida_pg_schema)
