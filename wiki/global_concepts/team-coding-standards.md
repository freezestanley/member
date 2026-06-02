# 团队通用编码规范

> 适用范围：所有项目，全员执行，不可绕过。

## 1. 语言规范

**全程使用中文**

- 所有与 Claude / AI 工具的对话、注释说明、任务描述均使用中文。
- 禁止在工作流程中切换为英文（代码变量名、API 字段名等技术标识符除外）。

## 2. 图标库规范

**禁止使用 `@ant-design/icons`，统一用 `lucide-react` 替代**

- 原因：减少依赖包体积，统一图标风格，避免 Ant Design 体系绑定。
- 迁移方式：将 `import { XxxOutlined } from '@ant-design/icons'` 替换为 `import { Xxx } from 'lucide-react'`。
- lucide-react 图标查询：https://lucide.dev/icons/

### 示例对照

| 禁止（ant-design/icons） | 替代（lucide-react） |
|--------------------------|----------------------|
| `<SearchOutlined />`     | `<Search />`         |
| `<DeleteOutlined />`     | `<Trash2 />`         |
| `<EditOutlined />`       | `<Pencil />`         |
| `<PlusOutlined />`       | `<Plus />`           |
| `<CloseOutlined />`      | `<X />`              |

---

*最后更新：2026-06-02*
