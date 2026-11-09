#pragma once

#include <array>
#include <cstdint>
#include <filesystem>
#include <optional>

namespace lm2 {
using SaveFormat = std::array<uint32_t, 4>;

void lock_save_directory(const std::filesystem::path &root);
std::optional<SaveFormat> read_save_format(const std::filesystem::path &save);
void format_save(const std::filesystem::path &save, const SaveFormat &format);
void backup_save_entry(const std::filesystem::path &save, const std::filesystem::path &entry);
bool is_save_format_file(const std::filesystem::path &path);
}
