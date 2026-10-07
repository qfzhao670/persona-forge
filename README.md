# Reddit 评论大模型预标注

`annotate_comments.py` 按 `Reddit_I.pdf` 和 `Reddit_II.pdf` 的定义，为 JSONL 中每条评论生成 32 个指标。默认配置已经指向：

- Base URL：`http://47.120.70.138:7113/v1`
- 模型：`min-lab-v1`
- 输入字段：`body`
- 输入文件：`input/random_100_comments.jsonl`
- 输出文件：`output/random_100_comments_prelabeled.jsonl`

W1/W2 使用固定版本的 NLTK POS/lemma 与 SUBTLEX-US Zipf 词频表；G1 使用仓库内固定、可审计的八类功能词词典。首次运行前安装依赖并准备本地资源：

```bash
python3 -m pip install -r requirements.txt
python3 scripts/setup_lexical_resources.py
```

安装脚本从 Ghent University 和 NLTK 官方地址下载资源，校验固定 SHA-256，并在 `resources/` 生成本地文件。生成的数据不会进入 Git；详细版本与目录说明见 `resources/README.md`。

## 运行

```bash
python3 annotate_comments.py --concurrency 4
```

不传 `--input` 和 `--output` 时，脚本默认读取 `input/random_100_comments.jsonl`，并把结果写入 `output/random_100_comments_prelabeled.jsonl`。也可以显式指定其他路径：

```bash
python3 annotate_comments.py \
  --input input/random_100_comments.jsonl \
  --output output/random_100_comments_prelabeled.jsonl
```

建议首次先做少量试标，人工检查后再跑 100 条：

```bash
python3 annotate_comments.py \
  --input input/random_100_comments.jsonl \
  --output output/prelabel_smoke.jsonl \
  --limit 5
```

使用阿里云 DashScope 云端模型时，先把 API Key 放入环境变量，再选择
`aliyun` provider（密钥不会写入命令历史或输出文件）：

```bash
export DASHSCOPE_API_KEY="<your-api-key>"
python3 annotate_comments.py \
  --provider aliyun \
  --input input/random_100_comments.jsonl \
  --output output/random_100_comments_qwen_prelabeled.jsonl \
  --concurrency 4
```
```bash
export DASHSCOPE_API_KEY="<your-api-key>"
python3 annotate_comments.py \
  --provider aliyun \
  --input input/random_100_comments.jsonl \
  --output output/prelabel_smoke.jsonl \
  --limit 5
```
该预设使用 `https://dashscope.aliyuncs.com/compatible-mode/v1` 和
`qwen3.8-flash`。如需切换其他 DashScope 模型，可同时传入
`--model 模型名`；`--base-url`、`--model` 和 `--api-key-env` 都可覆盖预设值。

脚本默认使用严格的 JSON Schema 结构化输出：

```json
{"type":"json_schema","json_schema":{"name":"...","strict":true,"schema":{...}}}
```

Schema 会约束两部分标注的字段、嵌套结构和基础类型，脚本随后仍会执行数值范围和跨字段一致性校验。提示词要求证据引用原文，但程序不再校验证据是否为原文子串。若服务端以 HTTP 400/422 表示不支持 JSON Schema，脚本会自动降级为 `{"type":"json_object"}`；若仍不支持，再降级为仅靠提示词约束的普通聊天请求。JSON Object 模式所需的 “JSON” 关键词已经包含在 System Message 中。也可增加 `--no-response-format`，从一开始就禁用结构化输出。

中断后可用同一输出路径加 `--resume`，脚本按原输入行号跳过已写入结果。

## 设计说明

- 每条评论发起两个独立请求，对应两份 PDF，避免 Part I/II 中同名的 `N1`、`P1` 冲突，也减少单次输出过长造成的漏项。
- 评论以 JSON 字符串置于用户消息中，系统提示明确把它视为不可信数据，不执行评论内指令。
- N1 分词、O1 段落、D2 MATTR、W1/W2 固定词频指标、G1 CDI、F1 固定音节启发式和所有派生公式由程序确定；模型负责其余需要语境的句法、词性、情绪、论证、立场、毒性和语用判断。
- 输出经过字段、枚举、数值范围及跨字段一致性校验。证据字段只校验字符串类型，不校验是否逐字存在于原文。失败会把其他校验错误反馈给模型重试；仍失败时写入 `status=error`，不会伪造标签。
- W1/W2 直接对 N1 token 运行固定 NLTK POS 标注，通过 WordNet lemma 和 SUBTLEX-US Zipf 表计算。G1 对同一 N1 token 流执行项目功能词词典精确匹配，计算八类百分比及 CDI。三项在模型输出后都会由程序强制回填。项目功能词词典不是 LIWC 词典复刻；F1 使用固定且可复现的后备音节规则。

代码按职责放在 `prelabeling/` 包中：

- `config.py`：默认配置、客户端配置对象及共享异常。
- `prompts.py`、`schemas.py`：模型提示词、输出结构和标签词表。
- `mechanics.py`：分词、分段、MATTR、音节等确定性计算。
- `lexical.py`：固定 POS/lemma 分析、SUBTLEX-US 加载、功能词词典加载及 W1/W2/G1 计算。
- `client.py`：OpenAI 兼容请求、结构化输出降级和重试。
- `validation.py`：模型输出校验及公式字段回填。
- `pipeline.py`：单条评论的两阶段标注流程。
- `storage.py`：JSONL 读取、格式化输出和断点续跑解析。
- `cli.py`：命令行参数及批量并发调度。

根目录的 `annotate_comments.py` 仅保留兼容入口，因此原有运行命令无需修改。

## 输出

输出按“一条评论一个 JSON 对象”连续写入，并保留输入对象的原字段。为方便人工审计，
`annotations.part_i` 和 `annotations.part_ii` 会展开为每个指标一行，指标内部保持紧凑；
`--resume` 同时支持这种多行格式和旧版的一行一条格式。每个对象新增：

- `annotations.part_i`：`Reddit_I.pdf` 的 16 个指标。
- `annotations.part_ii`：`Reddit_II.pdf` 的 16 个指标。
- `_prelabel_meta`：模型、提示词版本、原始行号、请求次数、token usage、资源状态或错误。

默认不会覆盖已有输出文件。需要遇到首个错误就停止时，增加 `--stop-on-error`；默认行为是记录错误后继续，便于完成整批预标注。
