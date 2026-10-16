{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if target.name == 'prod' -%}
        {%- set path = node.original_file_path -%}
        {%- if 'seeds' in path -%}
            financial_due_diligence_bronze
        {%- elif 'models/bronze' in path -%}
            financial_due_diligence_bronze
        {%- elif 'models/silver' in path -%}
            financial_due_diligence_silver
        {%- elif 'models/gold' in path -%}
            financial_due_diligence_gold
        {%- else -%}
            {{ target.schema }}
        {%- endif -%}
    {%- else -%}
        {#- Non-prod targets build every layer into one dev_<slug> schema so parallel
            branches never overwrite each other or the prod schemas. The pattern check
            stops a misconfigured dev target from writing into a prod schema. -#}
        {%- if not modules.re.match('^dev_[a-z0-9_]+$', target.schema) -%}
            {{ exceptions.raise_compiler_error("Non-prod target '" ~ target.name ~ "' must use a dev_<slug> schema, got '" ~ target.schema ~ "'") }}
        {%- endif -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
