#include "save_storage.h"

#include "log.h"

#include <windows.h>

#include <chrono>
#include <fstream>
#include <string>

namespace lm2 {
namespace {
namespace fs = std::filesystem;
constexpr auto format_name = ".lm2-archive-format";

fs::path make_snapshot_directory(const fs::path &parent, const char *prefix) {
    fs::create_directories(parent);
    auto now = std::chrono::system_clock::now().time_since_epoch().count();
    auto stem = std::string(prefix) + std::to_string(now) + "-" + std::to_string(GetCurrentProcessId());
    for (unsigned suffix = 0; suffix != 100; ++suffix) {
        auto path = parent / (stem + "-" + std::to_string(suffix));
        if (fs::create_directory(path)) return path;
    }
    fatal("Could not reserve a save snapshot directory");
}

void write_format(const fs::path &dir, const SaveFormat &format) {
    auto staged = dir / ".lm2-archive-format.pending";
    std::ofstream file(staged, std::ios::binary | std::ios::trunc);
    file.write(reinterpret_cast<const char *>(format.data()), sizeof format);
    file.close();
    if (!file) fatal("Could not write the LM2 archive format");
    fs::rename(staged, dir / format_name);
}
}

void lock_save_directory(const fs::path &root) {
    fs::create_directories(root);
    auto lock = root / "lm2-save.lock";
    // Keep the handle for the lifetime of the game.
    HANDLE handle = CreateFileW(lock.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS,
                                FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE) fatal("Cannot lock LM2 user data (Windows error %lu)", GetLastError());
}

std::optional<SaveFormat> read_save_format(const fs::path &save) {
    SaveFormat format{};
    std::ifstream file(save / format_name, std::ios::binary);
    if (!file.read(reinterpret_cast<char *>(format.data()), sizeof format)) return std::nullopt;
    if (file.peek() != std::char_traits<char>::eof() || format[3] > 1) return std::nullopt;
    return format;
}

bool is_save_format_file(const fs::path &path) {
    return path.filename() == format_name;
}

void backup_save_entry(const fs::path &save, const fs::path &entry) {
    if (!fs::exists(entry)) return;
    try {
        auto dir = make_snapshot_directory(save.parent_path() / "save-backups", "");
        fs::copy(entry, dir / entry.filename(), fs::copy_options::recursive);
        LOG("fs: previous save copied to %s", dir.string().c_str());
    } catch (const fs::filesystem_error &error) {
        fatal("Save backup failed: %s", error.what());
    }
}

void format_save(const fs::path &save, const SaveFormat &format) {
    try {
        if (fs::is_directory(save) && !fs::exists(save / format_name)) {
            // Keep profiles from builds that did not record format metadata.
            write_format(save, format);
            LOG("fs: recorded format metadata for existing LM2 save data");
            return;
        }
        auto staging = make_snapshot_directory(save.parent_path(), ".new-save-");
        write_format(staging, format);
        fs::path previous;
        if (fs::exists(save)) {
            previous = make_snapshot_directory(save.parent_path() / "save-backups", "") / "save";
            fs::rename(save, previous);
            LOG("fs: previous archive moved to %s", previous.string().c_str());
        }
        std::error_code error;
        fs::rename(staging, save, error);
        if (error) {
            if (!previous.empty()) {
                std::error_code restore_error;
                fs::rename(previous, save, restore_error);
            }
            fatal("Could not activate the LM2 save directory: %s", error.message().c_str());
        }
        for (const auto &entry : fs::directory_iterator(save.parent_path())) {
            if (!entry.path().filename().string().starts_with("save_secure_value_")) continue;
            backup_save_entry(save, entry.path());
            fs::remove(entry.path());
        }
        LOG("fs: formatted save data at %s", save.string().c_str());
    } catch (const fs::filesystem_error &error) {
        fatal("Save format failed: %s", error.what());
    }
}
}
