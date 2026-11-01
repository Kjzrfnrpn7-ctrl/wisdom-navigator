# RC4 → WA Integration Contract

## Parent
`KJ_WORLD_SYNTHESIS_RUNTIME_v0.1.3_COMPLETE_STANDALONE_RC4`
SHA-256 of FINAL_CANON package: `62496d53d4becb21257f959e17f8727512620b3ed18f1035392614b5c2b7820f`

## Hook
RC4 本体不修改。

仅新增后置 Hook：

```text
WS-21 PASS
→ WORLD_VALIDATED
→ [optional] WA Extension
→ ASSET_READY_WORLD
→ downstream production runtimes
```

## 不允许
- 不修改 WS-00～21 编号
- 不把 WA 注册为第23～29个一级符
- 不覆盖 KJ_WORLD_SYNTHESIS 的世界事实主权
- 不把 WIS 重新晋升成平行母 Runtime

## 回退
若 WA 发现世界级矛盾：
`WA-07 FAIL → RETURN_TO_WS_OWNER → WS Repair → WS-21 Revalidate → WORLD_VALIDATED → WA Recompute`
