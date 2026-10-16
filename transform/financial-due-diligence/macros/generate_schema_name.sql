{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if target.name == 'dev' -%}
        {#- Local dev builds every layer into one dev_<slug> schema so parallel branches
            never overwrite each other or the prod schemas. The pattern check stops a
            misconfigured dev target from writing into a prod schema. Only the explicit
            'dev' target takes this path: the Databricks job generates its own profile
            (target 'databricks_cluster'), so it must keep the layer routing below. -#}
        {%- if not modules.re.match('^dev_[a-z0-9_]+$', target.schema) -%}
            {{ exceptions.raise_compiler_error("Target 'dev' must use a dev_<slug> schema, got '" ~ target.schema ~ "'") }}
        {%- endif -%}
        {{ target.schema }}
    {%- else -%}
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
    {%- endif -%}
{%- endmacro %}
