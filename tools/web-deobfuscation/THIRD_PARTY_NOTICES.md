# Third-party notices

本地 safe AST runtime 锁定以下 MIT 组件，版本以 `package-lock.json` 为准：

| Package | Version | License | Repository |
|---------|---------|---------|------------|
| `@babel/parser` | 7.29.7 | MIT | https://github.com/babel/babel |
| `@babel/traverse` | 7.29.7 | MIT | https://github.com/babel/babel |
| `@babel/generator` | 7.29.7 | MIT | https://github.com/babel/babel |
| `@babel/types` | 7.29.7 | MIT | https://github.com/babel/babel |

完整传递依赖和 integrity 记录见 `package-lock.json`；当前传递依赖许可证为 MIT / ISC。本项目不复制 Babel 源码，也不引入 REstringer、webcrack runtime 或 `isolated-vm`。
